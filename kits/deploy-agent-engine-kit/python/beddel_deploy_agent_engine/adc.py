"""ADC (Application Default Credentials) validation for deploy-agent-engine-kit."""

from __future__ import annotations

import subprocess


def check_adc() -> dict[str, object]:
    """Check ADC configuration.

    Runs gcloud CLI commands to verify that Application Default Credentials
    are configured and retrieves the active GCP project ID.

    Returns a dict with:
        - configured (bool): Whether ADC is properly configured
        - project_id (str | None): The GCP project ID if configured
        - error (str | None): Error message if not configured

    Never raises — all errors are returned in the "error" field.
    """
    # Step 1: Check if ADC token is available
    try:
        token_result = subprocess.run(
            ["gcloud", "auth", "application-default", "print-access-token"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        return {
            "configured": False,
            "project_id": None,
            "error": (
                "gcloud CLI not found. Install the Google Cloud SDK: "
                "https://cloud.google.com/sdk/docs/install"
            ),
        }
    except subprocess.TimeoutExpired:
        return {
            "configured": False,
            "project_id": None,
            "error": "Timed out checking ADC credentials (gcloud did not respond within 10s).",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "configured": False,
            "project_id": None,
            "error": f"Unexpected error checking ADC: {exc}",
        }

    if token_result.returncode != 0:
        stderr = token_result.stderr.strip()
        return {
            "configured": False,
            "project_id": None,
            "error": (
                f"ADC not configured. Run: gcloud auth application-default login\n"
                f"Detail: {stderr}" if stderr else
                "ADC not configured. Run: gcloud auth application-default login"
            ),
        }

    # Step 2: Get the active project ID
    try:
        project_result = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return {
            "configured": True,
            "project_id": None,
            "error": "Timed out retrieving project ID from gcloud config.",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "configured": True,
            "project_id": None,
            "error": f"Unexpected error retrieving project ID: {exc}",
        }

    project_id: str | None = None
    if project_result.returncode == 0:
        project_id = project_result.stdout.strip() or None

    return {
        "configured": True,
        "project_id": project_id,
        "error": None,
    }
