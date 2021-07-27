"""Platform for HiMama sensor integration."""
import logging
from datetime import datetime, time, timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_ID, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .pymama import pymama_query

# TODO: add error logging
_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=15)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup HiMama sensors from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][entry.entry_id]

    email = config[CONF_EMAIL]
    password = config[CONF_PASSWORD]
    child_id = config[CONF_ID]

    hi_mama_data = HiMamaData(email, password, child_id)

    def update_sensors():
        hi_mama_data.update()

    await hass.async_add_executor_job(update_sensors)

    sensors = []

    for data in hi_mama_data.data.items():
        sensors.append(HiMamaSensor(data, hi_mama_data))

    async_add_entities(sensors, False)


class HiMamaSensor(Entity):
    """Representation of a HiMama Sensor."""

    def __init__(self, data, hi_mama_data) -> None:
        """Initialize the HiMama sensor."""
        self._state = None
        self._data = data
        self._hi_mama_data = hi_mama_data

    @property
    def name(self) -> str:
        """Return the name of the HiMama sensor."""
        if "At Daycare" in self._data[0]:
            return f"HiMama {self._data[0]}"
        return f"HiMama Latest {self._data[0]}"

    @property
    def state(self) -> datetime:
        """Return the state of the HiMama sensor."""
        return (
            self._data[1]
            if "At Daycare" in self._data[0]
            else self._data[1].get("Date")
        )

    @property
    def extra_state_attributes(self) -> str:
        """Return entity specific state attributes for HiMama."""
        if "At Daycare" in self._data[0]:
            return
        for (key, value) in self._data[1].items():
            if "Value" in key:
                new_value = ()
                for v in value:
                    if isinstance(v, time):
                        v = v.isoformat()
                    new_value = new_value + (v,)
                return {key.lower(): new_value}

    @property
    def icon(self) -> str:
        if self._data[0] == "Activities":
            return "mdi:run-fast"
        elif self._data[0] == "Bathroom":
            return "mdi:paper-roll-outline"
        elif self._data[0] == "Meals":
            return "mdi:food-apple-outline"
        elif self._data[0] == "Fluids":
            return "mdi:baby-bottle-outline"
        elif self._data[0] == "Mood":
            return "mdi:emoticon-outline"
        elif self._data[0] == "Naps":
            return "mdi:sleep"
        elif self._data[0] == "Notes":
            return "mdi:note-multiple-outline"
        elif self._data[0] == "At Daycare":
            return "mdi:map-marker-radius-outline"
        return "mdi:baby-face-outline"

    def update(self) -> None:
        """Update data from HiMama for the sensor."""
        self._hi_mama_data.update()
        for data in self._hi_mama_data.data.items():
            if self._data[0] in data[0]:
                self._data = data


# TODO: PYPI package
class HiMamaData:
    """Coordinate retrieving and updating data from HiMama."""

    def __init__(self, email: str, password: str, child_id: int) -> None:
        """Initialize the HiMamaData object."""
        self.data = None
        self._email = email
        self._password = password
        self._child_id = child_id

    def HiMamaQuery(self) -> dict:
        """Query HiMama for data."""
        pymama_data = pymama_query(self._email, self._password, self._child_id)
        pymama_latest = pymama_data.get("Latest")
        pymama_latest["At Daycare"] = pymama_data.get("At Daycare")
        return pymama_latest

    def update(self) -> None:
        """Update data from HiMama via HiMamaQuery."""
        self.data = self.HiMamaQuery()
