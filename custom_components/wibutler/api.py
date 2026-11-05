import aiohttp
import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional, List, Callable
from urllib.parse import urlparse

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Der Hub schickt jede Minute ein SYSTIME-Update. Drei Minuten Stille = Verbindung tot.
STREAM_IDLE_TIMEOUT = 180
# Login und Verbindungsaufbau duerfen nicht ewig haengen, wenn der Hub weg ist.
CONNECT_TIMEOUT = 30
# Wartezeit zwischen zwei Verbindungsversuchen: 5 s, verdoppelt bis 60 s
RECONNECT_DELAY_MIN = 5
RECONNECT_DELAY_MAX = 60
# Kurze Aussetzer (schnell wieder verbunden) machen die Entitaeten nicht "nicht verfuegbar"
UNAVAILABLE_AFTER = 60

class WibutlerHub:
    """Verwaltet die Kommunikation mit der Wibutler API, inklusive WebSockets."""

    def __init__(self, hass: HomeAssistant, host: str, port: int, username: str, password: str, verify_ssl: bool = False, use_ssl: bool = False):
        """Initialisiere Wibutler API-Verbindung."""
        self.hass = hass
        self.host = host
        self.port = port
        self.verify_ssl = verify_ssl
        self.use_ssl = use_ssl
        self.username = username
        self.password = password
        self.session = aiohttp.ClientSession()
        self.token: Optional[str] = None
        self.ws_task: Optional[asyncio.Task] = None
        self.listeners: List[Callable[[str, Any], None]] = []
        self.devices: Dict[str, Any] = {}
        # Stream zum Hub steht; False erst, wenn er laenger als UNAVAILABLE_AFTER weg ist
        self.connected = True
        self._lost_since: Optional[float] = None

        if self.use_ssl:
            self.schema = "https"
        else:
            self.schema = "http"

        # check if host has a scheme, if so set the baseUrl to the host without the scheme
        if urlparse(self.host).scheme:
            self.baseUrl = urlparse(self.host).hostname
        else:
            self.baseUrl = self.host

        if self.verify_ssl is False:
            _LOGGER.debug("🔓 SSL-Überprüfung ist deaktiviert (verify_ssl=False).")
            connector = aiohttp.TCPConnector(ssl=False)  # Deaktiviere SSL-Überprüfung
        else:
            _LOGGER.debug("🔒 SSL-Überprüfung ist aktiviert (verify_ssl=True).")
            connector = aiohttp.TCPConnector(ssl=True)  # Aktiviere SSL-Überprüfung

    async def authenticate(self, log_errors: bool = True) -> bool:
        """Authentifiziert sich bei der Wibutler API und speichert das Token.

        log_errors=False beim Wiederverbinden: der Stream meldet den Ausfall einmal selbst.
        """
        log_error = _LOGGER.error if log_errors else _LOGGER.debug
        url = f"{self.schema}://{self.baseUrl}:{self.port}/api/login"
        payload = {"username": self.username, "password": self.password}

        try:
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    # Upstream 62b6277: haengt der Login-Dienst, antwortet der Hub mit 200 und leerem Body
                    self.token = data.get("sessionToken") if data else None
                    if not self.token:
                        log_error("❌ API-Antwort enthält kein Token: %r", data)
                        return False
                    _LOGGER.info("✅ Erfolgreich authentifiziert!")
                    return True
                else:
                    log_error("❌ Authentifizierung fehlgeschlagen: %s", await response.text())
        except aiohttp.ClientError as err:
            log_error("❌ Verbindungsfehler mit Wibutler API: %s", err)
        return False

    async def _request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Sendet eine Anfrage an die Wibutler API."""
        if not self.token:
            _LOGGER.warning("Kein Token vorhanden, erneute Authentifizierung erforderlich.")
            if not await self.authenticate():
                return None

        url = f"{self.schema}://{self.baseUrl}:{self.port}/api/{endpoint}"
        headers = {"Authorization": f"Bearer {self.token}"}

        try:
            async with self.session.request(method, url, headers=headers, json=data) as response:
                if response.status in (200, 201):
                    # Workaround: aiohttp's response.json() bricht in HA 2026.5+
                    # (Python 3.14 / neueres aiohttp) bei grossen Wibutler-Responses
                    # mit JSONDecodeError ab. response.text() + json.loads ist robust.
                    return json.loads(await response.text())
                elif response.status == 401:
                    _LOGGER.warning("Token abgelaufen, erneute Authentifizierung erforderlich.")
                    self.token = None
                    return await self._request(method, endpoint, data)
                else:
                    _LOGGER.error("Fehlerhafte API-Antwort (%s): %s", response.status, await response.text())
        except aiohttp.ClientError as err:
            _LOGGER.error("Fehler bei der API-Anfrage: %s", err)
        return None

    async def get_devices(self) -> Optional[Dict[str, Any]]:
        """Holt die Liste der Geräte von der Wibutler API und gibt ein Dictionary zurück."""
        response = await self._request("GET", "devices")
        if isinstance(response, dict):
            return response.get("devices", {})
        _LOGGER.error("❌ Erwartete Dictionary-Antwort, aber erhalten: %s", type(response))
        return {}

    async def run_stream(self):
        """Haelt den WebSocket-Stream dauerhaft offen und verbindet nach jedem Abbruch neu.

        Nach einem Neustart des Hubs ist der alte Session-Token ungueltig. Deshalb vor jedem
        Verbindungsversuch neu einloggen und nach dem Wiederverbinden den vollen Stand holen.
        """
        delay = RECONNECT_DELAY_MIN

        while True:
            try:
                if self._lost_since is not None or not self.token:
                    self.token = None
                    await asyncio.wait_for(self.authenticate(log_errors=False), CONNECT_TIMEOUT)
                if self.token:
                    await self._listen()  # kehrt erst zurueck, wenn der Stream abbricht
            except asyncio.CancelledError:
                raise
            except Exception as err:  # Stream darf an keinem Fehler sterben
                _LOGGER.debug("WebSocket-Fehler: %r", err)

            if self._lost_since is None:
                self._lost_since = time.monotonic()
                delay = RECONNECT_DELAY_MIN
                _LOGGER.warning("⚠️ Stream zum Wibutler-Hub getrennt, verbinde neu")
            elif time.monotonic() - self._lost_since >= UNAVAILABLE_AFTER:
                self._set_connected(False)

            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_DELAY_MAX)

    async def _listen(self):
        """Eine Stream-Verbindung bis zu ihrem Ende lesen."""
        ws_protocol = "wss" if self.schema == "https" else "ws"
        ws_url = f"{ws_protocol}://{self.baseUrl}:{self.port}/api/stream/{self.token}"
        _LOGGER.debug("🔌 Verbindung zu WebSocket: %s", ws_url.replace(self.token, "***"))

        ws = await asyncio.wait_for(self.session.ws_connect(ws_url), CONNECT_TIMEOUT)
        async with ws:
            while True:
                msg = await asyncio.wait_for(ws.receive(), STREAM_IDLE_TIMEOUT)
                if msg.type != aiohttp.WSMsgType.TEXT:
                    _LOGGER.debug("WebSocket beendet: %s", msg.type)
                    return
                if self._lost_since is not None:
                    _LOGGER.info("✅ Stream zum Wibutler-Hub wieder verbunden nach %.0f s",
                                 time.monotonic() - self._lost_since)
                    self._lost_since = None
                    self._set_connected(True)
                    await self._resync()
                try:
                    data = json.loads(msg.data)
                    if "data" in data and "components" in data["data"]:
                        device_id = data["data"]["id"]
                        self._handle_ws_message(device_id, data["data"]["components"])
                except json.JSONDecodeError:
                    _LOGGER.error("❌ Fehler beim Parsen der WebSocket-Nachricht: %s", msg.data)

    async def _resync(self):
        """Nach einem Ausfall den vollen Geraetestand holen, Aenderungen waehrend der Pause nachziehen."""
        try:
            devices = await self.get_devices()
        except Exception as err:  # Abgleich ist Kuer, der Stream laeuft trotzdem weiter
            _LOGGER.warning("⚠️ Abgleich nach Wiederverbindung fehlgeschlagen: %r", err)
            return
        if not devices:
            return
        self.devices = devices
        for device_id, device in devices.items():
            self._handle_ws_message(device_id, device.get("components", []))

    def _set_connected(self, connected: bool):
        """Verbindungsstatus setzen und die Verfuegbarkeit der Entitaeten nachziehen."""
        if self.connected == connected:
            return
        self.connected = connected
        if not connected:
            _LOGGER.warning("⚠️ Wibutler-Hub seit %s s nicht erreichbar, Entitäten nicht verfügbar",
                            UNAVAILABLE_AFTER)
        for listener in self.listeners:
            if listener.hass is not None:
                listener.async_write_ha_state()

    def _handle_ws_message(self, device_id: str, components: List[Dict[str, Any]]):
        """Verarbeitet WebSocket-Nachrichten und benachrichtigt nur relevante Entitäten."""
        for listener in self.listeners:
            if listener._device_id == device_id:  # Nur relevante Entitäten aufrufen
                try:
                    listener.handle_ws_update(device_id, components)
                except Exception:  # eine kaputte Entitaet darf den Stream nicht beenden
                    _LOGGER.exception("❌ Update fuer %s fehlgeschlagen", device_id)

    def register_listener(self, entity) -> Callable[[], None]:
        """Registriert eine Entität für WebSocket-Updates. Rückgabe meldet sie wieder ab."""
        self.listeners.append(entity)

        def _remove():
            if entity in self.listeners:
                self.listeners.remove(entity)

        return _remove

    async def close(self):
        """Schließt die HTTP-Sitzung und beendet WebSocket-Verbindung."""
        if self.ws_task:
            self.ws_task.cancel()
        await self.session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()
