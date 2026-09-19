"""ViCare Circulation integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import config_entry_oauth2_flow

from .api import (
    ViessmannApiAuthenticationError,
    ViessmannApiClient,
    ViessmannApiError,
)
from .auth import RefreshingOAuthSession
from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_MODEL,
    CONF_DEVICE_SERIAL,
    CONF_GATEWAY_SERIAL,
    CONF_INSTALLATION_ID,
    PLATFORMS,
)
from .coordinator import ViCareCirculationCoordinator
from .models import Target

from .services import async_setup_services

type ViCareCirculationConfigEntry = ConfigEntry[ViCareCirculationCoordinator]

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up ViCare Circulation services."""
    await async_setup_services(hass)
    return True

async def async_setup_entry(
    hass: HomeAssistant, entry: ViCareCirculationConfigEntry
) -> bool:
    """Set up ViCare Circulation from a config entry."""
    try:
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, entry
            )
        )
    except ValueError as err:
        raise ConfigEntryAuthFailed("OAuth implementation unavailable") from err

    oauth_session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    api = ViessmannApiClient(RefreshingOAuthSession(hass, entry, oauth_session))
    target = Target(
        installation_id=entry.data[CONF_INSTALLATION_ID],
        gateway_serial=entry.data[CONF_GATEWAY_SERIAL],
        device_id=entry.data[CONF_DEVICE_ID],
        device_serial=entry.data.get(CONF_DEVICE_SERIAL),
        model=entry.data.get(CONF_DEVICE_MODEL),
    )

    try:
        await oauth_session.async_ensure_token_valid()
        await api.async_validate_target(target)
    except (OAuth2TokenRequestReauthError, ViessmannApiAuthenticationError) as err:
        raise ConfigEntryAuthFailed("Viessmann authentication failed") from err
    except OAuth2TokenRequestError as err:
        raise ConfigEntryNotReady("Unable to refresh Viessmann OAuth token") from err
    except ViessmannApiError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = ViCareCirculationCoordinator(hass, entry, api, target)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ViCareCirculationConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
