import logging
from homeassistant.components.switch import SwitchEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Wibutler switches from a config entry."""
    hub = hass.data[DOMAIN]["hub"]
    devices = hub.devices

    switches = []
    for device_id, device in devices.items():
        if device.get("type") == "SwitchingRelays":
            switches.append(WibutlerSwitch(hub, device))

    async_add_entities(switches, True)

class WibutlerSwitch(SwitchEntity):
    """Representation of a Wibutler switch."""

    def __init__(self, hub, device):
        """Initialize the switch."""
        self._hub = hub
        self._device = device
        self._device_id = device["id"]
        self._attr_name = device['name']
        self._attr_unique_id = f"{device['id']}_{device['name']}"
        self._state = None
        self._fetch_state(device.get("components", []))

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        data = {"value": "ON", "type": "switch"}
        url = f"devices/{self._device_id}/components/SWT"

        response = await self._hub._request("PATCH", url, data)

        if response:
            _LOGGER.info("🔌 Switch %s eingeschaltet", self._attr_name)
            self._state = True
            self.async_write_ha_state()
        else:
            _LOGGER.error("❌ Fehler beim Einschalten des Switch %s", self._attr_name)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        data = {"value": "OFF", "type": "switch"}
        url = f"devices/{self._device_id}/components/SWT"

        response = await self._hub._request("PATCH", url, data)

        if response:
            _LOGGER.info("🔌 Switch %s ausgeschaltet", self._attr_name)
            self._state = False
            self.async_write_ha_state()
        else:
            _LOGGER.error("❌ Fehler beim Ausschalten des Switch %s", self._attr_name)

    def _fetch_state(self, components):
        """Aktualisiert den Zustand basierend auf den Gerätedaten."""
        for component in components:
            if component.get("name") == "STATE":
                value = component.get("value")
                _LOGGER.debug(f"🏠 STATE von {self._attr_name}: {value}")

                # STATE bestimmt den tatsächlichen Zustand
                self._state = value == "1"  # Falls "1" für "An" steht

            if component.get("name") == "SWT":
                value = component.get("value")

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