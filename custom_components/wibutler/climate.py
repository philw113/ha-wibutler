import logging
from typing import Optional, Tuple, List, Dict, Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVACMode,
    ClimateEntityFeature,
    PRESET_COMFORT,
    PRESET_ECO,
)
from homeassistant.const import UnitOfTemperature
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Modus-Komponenten lassen wir als Bonus drin (viele Geräte lehnen sie ab)
MODE_COMPONENT_CANDIDATES: Tuple[str, ...] = (
    "RTSPMODE",
    "_prf_0_RTSPMODE",
    "_prf_1_RTSPMODE",
    "_prf_2_RTSPMODE",
    "_prf_3_RTSPMODE",
    "MODE",
    "OPMODE",
    "PROGRAMMODE",
)

# Komfort-/Eco-Setpoint-Kandidaten
CTSP_CANDIDATES_EXACT: Tuple[str, ...] = (
    "CTSP",
    "_prf_0_CTSP",
    "_prf_1_CTSP",
    "_prf_2_CTSP",
    "_prf_3_CTSP",
)
ETSP_CANDIDATES_EXACT: Tuple[str, ...] = (
    "ETSP",
    "_prf_0_ETSP",
    "_prf_1_ETSP",
    "_prf_2_ETSP",
    "_prf_3_ETSP",
    "ECOTSP",
    "_prf_0_ECOTSP",
    "_prf_1_ECOTSP",
    "_prf_2_ECOTSP",
    "_prf_3_ECOTSP",
    "ECO_SP",
    "_prf_0_ECO_SP",
    "_prf_1_ECO_SP",
    "_prf_2_ECO_SP",
    "_prf_3_ECO_SP",
    "ECOSP",
    "_prf_0_ECOSP",
    "_prf_1_ECOSP",
    "_prf_2_ECOSP",
    "_prf_3_ECOSP",
    "ESP",
    "_prf_0_ESP",
    "_prf_1_ESP",
    "_prf_2_ESP",
    "_prf_3_ESP",
)
ETSP_SUBSTRINGS: Tuple[str, ...] = ("ETSP", "ECO", "ESP")

# Fallback-Strategie, wenn (C/E)TSP nicht verfügbar ist
ECO_FALLBACK_DELTA_C = 2.0     # Eco = TSP - 2.0 °C
COMFORT_FALLBACK_C   = 21.0    # Komfort-Standard (°C)
MIN_C = 5.0
MAX_C = 30.0

def _deg_to_raw(deg_c: float) -> int:
    # (°C - 10) * 2
    return int(round((float(deg_c) - 10.0) * 2.0))

def _raw_to_deg(raw: int) -> float:
    # raw/2 + 10
    return (int(raw) / 2.0) + 10.0

def _clamp_c(deg_c: float) -> float:
    return max(MIN_C, min(MAX_C, deg_c))


async def async_setup_entry(hass, entry, async_add_entities):
    hub = hass.data[DOMAIN]["hub"]
    devices = hub.devices

    entities: List[WibutlerClimate] = []
    for _, device in devices.items():
        if device.get("type") in ["RoomOperatingPanels", "FloorHeatingController"]:
            entities.append(WibutlerClimate(hub, device))

    if not entities:
        _LOGGER.info("WiButler Climate: keine passenden Geräte gefunden.")
    else:
        _LOGGER.debug("WiButler Climate: %d Gerät(e) werden angelegt.", len(entities))
    async_add_entities(entities, True)


class WibutlerClimate(ClimateEntity):
    """Minimal & robust: Presets über (C/E)TSP, RTSPMODE optional, Toleranzanzeige."""

    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    _attr_preset_modes = [PRESET_COMFORT, PRESET_ECO]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = MIN_C
    _attr_max_temp = MAX_C

    def __init__(self, hub, device: Dict[str, Any]):
        self._hub = hub
        self._device = device
        self._device_id: str = device["id"]
        self._attr_name = device["name"]
        self._attr_unique_id = device["id"]

        # Caches
        self._mode_component: Optional[str] = None
        self._ctsp_comp: Optional[str] = None
        self._etsp_comp: Optional[str] = None
        self._raw_tsp: Optional[str] = None
        self._raw_ctsp: Optional[str] = None
        self._raw_etsp: Optional[str] = None

        self._attr_current_temperature: Optional[float] = None
        self._attr_target_temperature: Optional[float] = None
        self._attr_preset_mode: Optional[str] = None

        self._fetch_state(device.get("components", []))

    # ---- HA properties ----
    @property
    def hvac_mode(self) -> HVACMode:
        return HVACMode.HEAT

    @property
    def preset_mode(self) -> Optional[str]:
        return self._attr_preset_mode

    @property
    def current_temperature(self) -> Optional[float]:
        return self._attr_current_temperature

    @property
    def target_temperature(self) -> Optional[float]:
        return self._attr_target_temperature

    @property
    def icon(self) -> str:
        return "mdi:radiator"

    # ---- Commands ----
    async def async_set_temperature(self, **kwargs):
        if "temperature" not in kwargs:
            return
        deg_c = _clamp_c(float(kwargs["temperature"]))
        raw = _deg_to_raw(deg_c)
        payload = {"type": "numeric", "value": str(raw)}
        url = f"devices/{self._device_id}/components/TSP"
        _LOGGER.debug("📡 [%s] TSP setzen: %.1f°C → raw=%s → %s %s", self._attr_name, deg_c, raw, url, payload)
        resp = await self._hub._request("PATCH", url, payload)
        if resp:
            self._raw_tsp = str(raw)
            self._attr_target_temperature = deg_c
            self._update_preset_guess()
            self.async_write_ha_state()
            _LOGGER.info("✅ [%s] Zieltemp gesetzt: %.1f°C (TSP=%s)", self._attr_name, deg_c, raw)
        else:
            _LOGGER.error("❌ [%s] Zieltemp setzen fehlgeschlagen", self._attr_name)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode not in (PRESET_COMFORT, PRESET_ECO):
            _LOGGER.warning("Unbekanntes Preset: %s", preset_mode)
            return

        # 1) Bonus: RTSPMODE (viele Geräte lehnen mit 422 ab)
        comp = self._mode_component or self._detect_mode_component(self._device.get("components", []))
        if comp:
            for comp_try in [comp, *MODE_COMPONENT_CANDIDATES]:
                for t, v in (("enum", "Komfort" if preset_mode == PRESET_COMFORT else "Sparen"),
                             ("text", "Komfort" if preset_mode == PRESET_COMFORT else "Sparen"),
                             ("enum", "1" if preset_mode == PRESET_COMFORT else "2"),
                             ("numeric", "1" if preset_mode == PRESET_COMFORT else "2")):
                    payload = {"type": t, "value": v}
                    url = f"devices/{self._device_id}/components/{comp_try}"
                    _LOGGER.debug("📡 [%s] Bonus RTSPMODE: %s → %s %s", self._attr_name, comp_try, url, payload)
                    try:
                        if await self._hub._request("PATCH", url, payload):
                            self._attr_preset_mode = preset_mode
                            self._mode_component = comp_try
                            self.async_write_ha_state()
                            _LOGGER.info("✅ [%s] Preset via %s gesetzt (%s=%s)",
                                         self._attr_name, comp_try, t, v)
                            return
                    except Exception:
                        continue
            _LOGGER.debug("ℹ️ [%s] RTSPMODE/Profil abgelehnt – setze per Setpoints.", self._attr_name)

        # 2) Primärpfad: TSP ← (C/E)TSP (mit Fallbacks, falls 0/fehlt)
        ctsp_name, etsp_name = await self._locate_setpoint_components()

        if preset_mode == PRESET_COMFORT:
            raw = await self._resolve_comfort_raw(ctsp_name)
            src = self._ctsp_comp or "comfort_fallback"
        else:
            raw = await self._resolve_eco_raw(etsp_name)
            src = self._etsp_comp or "eco_fallback"

        if raw is None:
            _LOGGER.error("❌ [%s] Kein gültiger %s-Setpoint verfügbar → Abbruch",
                          self._attr_name, "Komfort" if preset_mode == PRESET_COMFORT else "Eco")
            return

        payload = {"type": "numeric", "value": str(raw)}
        url = f"devices/{self._device_id}/components/TSP"
        _LOGGER.debug("📡 [%s] TSP ← %s (%s)", self._attr_name, src, payload)
        if await self._hub._request("PATCH", url, payload):
            self._attr_preset_mode = preset_mode
            self._raw_tsp = str(raw)
            self._attr_target_temperature = _raw_to_deg(raw)
            self.async_write_ha_state()
            _LOGGER.info("✅ [%s] Preset %s via TSP←%s gesetzt (raw=%s)",
                         self._attr_name, preset_mode, src, raw)
        else:
            _LOGGER.error("❌ [%s] Fallback TSP←%s fehlgeschlagen", self._attr_name, src)

    # ---- State handling ----
    def _fetch_state(self, components: List[Dict[str, Any]]) -> None:
        for c in components:
            name = c.get("name")
            value = c.get("value")

            if name == "RTMP":
                try:
                    self._attr_current_temperature = int(value) / 100
                except Exception:
                    pass
            elif name == "TMP":
                try:
                    self._attr_current_temperature = int(value) / 100
                except Exception:
                    pass
            elif name == "TSP":
                try:
                    self._raw_tsp = str(value)
                    self._attr_target_temperature = _raw_to_deg(int(value))
                except Exception:
                    pass
            elif name in CTSP_CANDIDATES_EXACT:
                self._ctsp_comp = self._ctsp_comp or name
                try:
                    self._raw_ctsp = str(value)
                except Exception:
                    pass
            elif name in ETSP_CANDIDATES_EXACT or self._matches_etsp_like(name):
                self._etsp_comp = self._etsp_comp or name
                try:
                    self._raw_etsp = str(value)
                except Exception:
                    pass
            elif name in MODE_COMPONENT_CANDIDATES:
                self._mode_component = self._mode_component or name
                # nur Anzeige-Parsing (einige liefern Text, einige 1/2)
                try:
                    s = str(value).strip().lower()
                    if s.startswith("komf") or s == "1":
                        self._attr_preset_mode = PRESET_COMFORT
                    elif s.startswith(("spar", "eco")) or s == "2":
                        self._attr_preset_mode = PRESET_ECO
                except Exception:
                    pass

        self._update_preset_guess()

    def _update_preset_guess(self) -> None:
        # ±0,5°C Toleranz
        def near(a: Optional[str], b: Optional[str]) -> bool:
            try:
                return a is not None and b is not None and abs(int(a) - int(b)) <= 1
            except Exception:
                return False

        before = self._attr_preset_mode
        if self._raw_tsp is not None:
            if near(self._raw_tsp, self._raw_etsp):
                self._attr_preset_mode = PRESET_ECO
            elif near(self._raw_tsp, self._raw_ctsp):
                self._attr_preset_mode = PRESET_COMFORT

        if before != self._attr_preset_mode:
            _LOGGER.debug("🔁 [%s] Preset-Heuristik: %s → %s (TSP=%r, CTSP=%r, ETSP=%r)",
                          self._attr_name, before, self._attr_preset_mode,
                          self._raw_tsp, self._raw_ctsp, self._raw_etsp)

    def _detect_mode_component(self, components: List[Dict[str, Any]]) -> Optional[str]:
        names = [c.get("name") for c in components if c.get("name")]
        for cand in MODE_COMPONENT_CANDIDATES:
            if cand in names:
                return cand
        return None

    def _matches_etsp_like(self, name: Optional[str]) -> bool:
        if not name:
            return False
        up = name.upper()
        return any(key in up for key in ETSP_SUBSTRINGS)

    # ---- Helpers ----
    async def _locate_setpoint_components(self) -> Tuple[Optional[str], Optional[str]]:
        if self._ctsp_comp and self._etsp_comp:
            return self._ctsp_comp, self._etsp_comp

        try:
            data = await self._hub._request("GET", f"devices/{self._device_id}")
            comps = data.get("components", []) if data else []
        except Exception:
            comps = []

        names = [c.get("name") for c in comps if c.get("name")]

        for cand in CTSP_CANDIDATES_EXACT:
            if cand in names:
                self._ctsp_comp = cand
                break

        if not self._etsp_comp:
            for cand in ETSP_CANDIDATES_EXACT:
                if cand in names:
                    self._etsp_comp = cand
                    break
        if not self._etsp_comp:
            # heuristisch: bestes Match nach Substrings
            scored: List[Tuple[int, str]] = []
            for n in names:
                up = n.upper()
                score = 0
                for i, key in enumerate(ETSP_SUBSTRINGS):
                    if key in up:
                        score = max(score, len(ETSP_SUBSTRINGS) - i)
                if score:
                    scored.append((score, n))
            scored.sort(reverse=True)
            if scored:
                self._etsp_comp = scored[0][1]

        # cached Werte
        if self._ctsp_comp:
            self._raw_ctsp = self._extract_value(comps, self._ctsp_comp) or self._raw_ctsp
        if self._etsp_comp:
            self._raw_etsp = self._extract_value(comps, self._etsp_comp) or self._raw_etsp

        _LOGGER.debug("🧭 [%s] Setpoints erkannt: CTSP=%s(raw=%r)  ETSP=%s(raw=%r)",
                      self._attr_name, self._ctsp_comp, self._raw_ctsp, self._etsp_comp, self._raw_etsp)

        return self._ctsp_comp, self._etsp_comp

    async def _resolve_eco_raw(self, etsp_name: Optional[str]) -> Optional[int]:
        """Eco-raw ermitteln – aus ETSP wenn vorhanden, sonst TSP-Delta."""
        raw = None
        if etsp_name:
            v = await self._read_component_value(etsp_name)
            try:
                if v is not None and int(v) > 0:
                    raw = int(v)
                    self._raw_etsp = str(raw)
            except Exception:
                pass
        if raw is None:
            # Fallback: Eco = aktuelles TSP - 2.0°C
            curr_raw = await self._current_tsp_raw()
            if curr_raw is not None:
                eco_deg = _clamp_c(_raw_to_deg(curr_raw) - ECO_FALLBACK_DELTA_C)
                raw = _deg_to_raw(eco_deg)
        return raw

    async def _resolve_comfort_raw(self, ctsp_name: Optional[str]) -> Optional[int]:
        """Komfort-raw ermitteln – aus CTSP wenn vorhanden, sonst Standard 21°C."""
        raw = None
        if ctsp_name:
            v = await self._read_component_value(ctsp_name)
            try:
                if v is not None and int(v) > 0:
                    raw = int(v)
                    self._raw_ctsp = str(raw)
            except Exception:
                pass
        if raw is None:
            raw = _deg_to_raw(COMFORT_FALLBACK_C)
        return raw

    async def _current_tsp_raw(self) -> Optional[int]:
        if self._raw_tsp is not None:
            try:
                return int(self._raw_tsp)
            except Exception:
                pass
        # Live lesen
        v = await self._read_component_value("TSP")
        try:
            return int(v) if v is not None else None
        except Exception:
            return None

    def _extract_value(self, comps: List[Dict[str, Any]], name: str) -> Optional[str]:
        for c in comps:
            if c.get("name") == name:
                return c.get("value")
        return None

    async def _read_component_value(self, comp_name: str) -> Optional[str]:
        try:
            data = await self._hub._request("GET", f"devices/{self._device_id}")
            comps = data.get("components", []) if data else []
            return self._extract_value(comps, comp_name)
        except Exception as e:
            _LOGGER.debug("Lesen %s fehlgeschlagen [%s]: %s", comp_name, self._attr_name, e)
            return None

    # ---- WS / Updates ----
    async def async_added_to_hass(self):
        self._hub.register_listener(self)

    def handle_ws_update(self, device_id, components):
        if device_id != self._device_id:
            return
        self._fetch_state(components)
        self.async_write_ha_state()
