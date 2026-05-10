"""Beddel GitHub auth kit."""

from beddel_auth_github.provider import (
    CredentialData,
    check_token_validity,
    delete_credentials,
    get_auth_headers,
    get_github_user,
    initiate_device_flow,
    load_credentials,
    poll_for_token,
    save_credentials,
)

__all__ = [
    "CredentialData",
    "check_token_validity",
    "delete_credentials",
    "get_auth_headers",
    "get_github_user",
    "initiate_device_flow",
    "load_credentials",
    "poll_for_token",
    "save_credentials",
]
