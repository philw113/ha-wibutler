import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Wibutler sensors from a config entry."""
    hub = hass.data[DOMAIN]["hub"]
    devices = hub.devices

    sensors = []
    for device_id, device in devices.items():
        if device.get("type") not in ["FloorHeatingController"]:
            continue

        # Extrahiere alle "name"-Werte aus outputs
        outputs = {output["name"] for output in device.get("outputs", [])}

        for component in device.get("components", []):
            if component.get("readonly") == True and component.get("name") in outputs:  # Nur wenn Name in outputs existiert
                sensors.append(WibutlerSensor(hub, device, component))

    async_add_entities(sensors, True)

class WibutlerSensor(SensorEntity):
    def __init__(self, hub, device, component):
        """Initialize the sensor."""
        from homeassistant.const import PERCENTAGE
        from homeassistant.util.unit_system import UnitOfTemperature

        self._hub = hub
        self._device = device
        self._component = component
        self._device_id = device['id']
        self._component_name = component['name']
        self._state = component['value']
        self._attr_name = f"{device['name']} - {component['text']}"
        self._attr_unique_id = f"{device['id']}_{component['name']}"
        self._attr_native_value = component.get("value")

        # Einheit bestimmen
        if "temperature" in component.get("text", "").lower():
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            raw_value = component.get("value")
            self._attr_native_value = int(self._attr_native_value) / 100
        elif "switch-on time" in component.get("text", "").lower():
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_native_value = int(self._attr_native_value)
        elif "humidity" in component.get("text", "").lower():
            self._attr_native_unit_of_measurement = PERCENTAGE
        else:
            self._attr_native_unit_of_measurement = None  # Keine spezifische Einheit

    def _fetch_state(self, components):
        """Holt den neuen Zustand aus WebSocket-Daten und setzt den Status korrekt."""
        for component in components:
            if component.get("name") == self._component_name:
                self._state = component.get("value")
                self._attr_native_value = component.get("value")

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
