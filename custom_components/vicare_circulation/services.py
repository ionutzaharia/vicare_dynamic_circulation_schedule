"""Services for ViCare Circulation."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_extract_config_entry_ids

from .api import ViessmannApiError
from .const import DAYS, DOMAIN
from .coordinator import ViCareCirculationCoordinator
from .models import Schedule

SERVICE_SET_SCHEDULE = "set_circulation_schedule"

TIME_PATTERN = r"^(?:[01]\d|2[0-3]):[0-5]\d$"

SCHEDULE_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Required("start"): vol.All(str, vol.Match(TIME_PATTERN)),
        vol.Required("end"): vol.All(str, vol.Match(TIME_PATTERN)),
        vol.Optional("mode", default="on"): cv.string,
    }
)

DAY_SCHEMA = vol.All(
    vol.ensure_list,
    [SCHEDULE_ENTRY_SCHEMA],
)

SET_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Optional(day): DAY_SCHEMA
        for day in DAYS
    }
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register ViCare Circulation services."""

    async def async_set_schedule(call: ServiceCall) -> None:
        """Set the complete circulation schedule."""
        entry_ids = await async_extract_config_entry_ids(call)

        if not entry_ids:
            raise HomeAssistantError(
                "Target the ViCare Circulation device or one of its entities."
            )

        if len(entry_ids) > 1:
            raise HomeAssistantError(
                "The service call targets more than one ViCare Circulation config entry."
            )

        entry_id = next(iter(entry_ids))
        entry = hass.config_entries.async_get_entry(entry_id)

        if entry is None or entry.domain != DOMAIN:
            raise HomeAssistantError(
                "The targeted ViCare Circulation config entry was not found."
            )

        coordinator: ViCareCirculationCoordinator | None = entry.runtime_data

        if coordinator is None:
            raise HomeAssistantError(
                "ViCare Circulation is not currently loaded."
            )

        schedule: Schedule = {}
        
        for day in DAYS:
            entries = call.data.get(day, [])
        
            schedule[day] = [
                {
                    "start": item["start"],
                    "end": item["end"],
                    "mode": item.get("mode", "on"),
                }
                for item in entries
            ]

        # The Viessmann API expects the complete weekly schedule.
        #
        # For this integration we therefore fill omitted days from the
        # currently active schedule.
        current = coordinator.data.schedule if coordinator.data else None

        if current:
            for day in DAYS:
                if day not in schedule:
                    schedule[day] = current.get(day, [])

        try:
            confirmed = await coordinator.async_write_schedule(schedule)
        except (ViessmannApiError, ConfigEntryAuthFailed) as err:
            raise HomeAssistantError(
                f"Unable to write circulation schedule: {err}"
            ) from err

        if not confirmed:
            # The API accepted the command but the read endpoint has not
            # confirmed it yet. The coordinator already scheduled a follow-up
            # refresh, so this is not necessarily an error.
            return

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SCHEDULE,
        async_set_schedule,
        schema=SET_SCHEDULE_SCHEMA,
    )
