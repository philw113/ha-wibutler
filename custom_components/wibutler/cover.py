import logging
from homeassistant.components.cover import CoverEntity, CoverDeviceClass, CoverEntityFeature
from .const import DOMAIN
import asyncio

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Wibutler cover devices from a config entry."""
    hub = hass.data[DOMAIN]["hub"]
    devices = hub.devices

    covers = []
    for device_id, device in devices.items():
        if device.get("type") == "Blind":
            covers.append(WibutlerCover(hub, device))

    async_add_entities(covers, True)

class WibutlerCover(CoverEntity):
    """Representation of a Wibutler Cover Device."""

    def __init__(self, hub, device):
        """Initialize the cover device."""
        self._hub = hub
        self._device = device
        self._device_id = device['id']
        self._state = None
        self._attr_name = device['name']
        self._attr_unique_id = device['id']
        self._attr_device_class = CoverDeviceClass.SHUTTER
        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP | CoverEntityFeature.SET_POSITION
        )
        self._position = None
        self._last_command = None  # Speichert den letzten gesendeten Wert (ON oder OFF)
        self._fetch_state(device.get("components", []))

    def _fetch_state(self, components):
        """Initialisiert die aktuelle Position aus den Gerätedaten.

        CURPOS ist die echte Position, die der Aktor aus seiner Laufzeit rechnet.
        POS ist nur der zuletzt gesendete Sollwert und dient als Rueckfall fuer Aktoren ohne CURPOS.
        """
        values = {c.get("name"): c.get("value") for c in components}
        if "CURPOS" in values:
            self._has_curpos = True
            self._position = self._to_int(values["CURPOS"])
        elif "POS" in values and not self._has_curpos:
            self._position = self._to_int(values["POS"])
        if "STATE" in values:
            self._state = values["STATE"]

    _has_curpos = False

    @staticmethod
    def _to_int(value):
        try:
            return int(value)  # Prozentwert (0-100), Wibutler zaehlt % geschlossen
        except (ValueError, TypeError):
            return None

    @property
    def current_cover_position(self):
        """Gibt die Position des Covers zurück (inverted für Home Assistant)."""
        if self._position is None:
            return None
        return 100 - self._position  # 🔄 Wibutler liefert "closed %", wir brauchen "open %"

    @property
    def is_opening(self) -> bool | None:
        """Gibt zurück, ob das Cover gerade öffnet."""
        # Der Hub meldet das Fahrtende nicht immer: in der Endlage gilt die Fahrt als beendet
        return self._state == "Opening" and self._position != 0

    @property
    def is_closing(self) -> bool | None:
        """Gibt zurück, ob das Cover gerade schließt."""
        return self._state == "Closing" and self._position != 100

    @property
    def is_stopped(self) -> bool | None:
        """Gibt zurück, ob das Cover gerade schließt."""
        return self._state == "Stopped"

    @property
    def is_closed(self) -> bool | None:
        """Gibt zurück, ob das Cover komplett geschlossen ist."""
        return self._position == 100  # Wibutler gibt 100% closed zurück

    async def async_set_cover_position(self, **kwargs):
        """Setzt die Position des Covers (umgekehrte Werte für Wibutler)."""
        if "position" not in kwargs:
            return

        new_position = 100 - int(kwargs["position"])  # 🔄 Umkehren vor dem Senden
        data = {
            "value": str(new_position),
            "type": "numeric"
        }

        _LOGGER.debug(f"📡 PATCH-Request an API: URL=devices/{self._device_id}/components/POS, Data={data}")

        url = f"devices/{self._device_id}/components/POS"
        response = await self._hub._request("PATCH", url, data)

        if response:
            _LOGGER.info("📟 Position für %s auf %s%% gesetzt", self._attr_name, 100 - new_position)
            self._position = new_position
            self.async_write_ha_state()
        else:
            _LOGGER.error("❌ Fehler beim Setzen der Position für %s", self._attr_name)

    async def async_open_cover(self, **kwargs):
        """Öffnet das Cover vollständig."""
        data = {"value": "ON", "type": "switch"}
        url = f"devices/{self._device_id}/components/SWT_POS"

        response = await self._hub._request("PATCH", url, data)

        if response:
            _LOGGER.info("⬆️ Cover %s geöffnet", self._attr_name)
            self._position = 0  # Offen = 0% geschlossen
            self._last_command = "ON"  # Letzter gesendeter Befehl speichern
            self.async_write_ha_state()
        else:
            _LOGGER.error("❌ Fehler beim Öffnen des Covers %s", self._attr_name)

    async def async_close_cover(self, **kwargs):
        """Schließt das Cover vollständig."""
        data = {"value": "OFF", "type": "switch"}
        url = f"devices/{self._device_id}/components/SWT_POS"

        response = await self._hub._request("PATCH", url, data)

        if response:
            _LOGGER.info("⬇️ Cover %s geschlossen", self._attr_name)
            self._position = 100  # Geschlossen = 100% geschlossen
            self._last_command = "OFF"  # Letzter gesendeter Befehl speichern
            self.async_write_ha_state()
        else:
            _LOGGER.error("❌ Fehler beim Schließen des Covers %s", self._attr_name)

    async def async_stop_cover(self, **kwargs):
        """Stoppt das Cover, indem der letzte Befehl zweimal gesendet wird."""
        if self._last_command is None:
            _LOGGER.warning("⚠️ Kein letzter Befehl bekannt, kann nicht stoppen!")
            return

        data = {"value": self._last_command, "type": "switch"}
        url = f"devices/{self._device_id}/components/SWT_POS"

        # Erster Versuch
        response = await self._hub._request("PATCH", url, data)

        if not response:
            _LOGGER.error("❌ Fehler beim ersten Stop-Befehl für %s", self._attr_name)
            return

        await asyncio.sleep(0.5)  # 🔄 500 ms warten (falls nötig anpassen)

        # Zweiter Versuch
        response = await self._hub._request("PATCH", url, data)

        if response:
            _LOGGER.info("⏹️ Cover %s gestoppt (erneut %s gesendet)", self._attr_name, self._last_command)
            self.async_write_ha_state()
        else:
            _LOGGER.error("❌ Fehler beim zweiten Stop-Befehl für %s", self._attr_name)

    @property
    def available(self) -> bool:
        """Nicht verfügbar, solange der Stream zum Hub länger getrennt ist."""
        return self._hub.connected

    async def async_added_to_hass(self):
        """Register for WebSocket updates."""
        self.async_on_remove(self._hub.register_listener(self))

    def handle_ws_update(self, device_id, components):
        """Process WebSocket update."""
        self._fetch_state(components)
        self.async_write_ha_state()