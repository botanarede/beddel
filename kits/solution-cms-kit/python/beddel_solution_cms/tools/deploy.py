"""deploy_site + provision_firebase tools — Firebase/gcloud CLI wrapping.

Wraps ``firebase deploy`` and ``gcloud`` commands via SafeSubprocessRunner
for deploying tenant static sites and provisioning new Firebase projects.
Both tools use Application Default Credentials (ADC).
"""

from __future__ import annotations

import os
import re

from beddel_solution_cms._errors import (
    CMS_DEPLOY_FAILED,
    CMS_PROVISION_FAILED,
    CMSError,
)
from beddel_solution_cms.tenant_context import get_kit_root, validate_tenant_id
from beddel.utils.subprocess import SafeSubprocessRunner

__all__ = ["deploy_site", "provision_firebase"]

_DEPLOY_TIMEOUT = 120
_PROVISION_CMD_TIMEOUT = 60

# Regex to extract hosting URL from firebase deploy stdout
_HOSTING_URL_RE = re.compile(r"Hosting URL:\s*(https?://\S+)")


def deploy_site(
    tenant_id: str,
    project_id: str,
    *,
    hosting_target: str | None = None,
) -> dict:
    """Deploy a tenant's static site to Firebase Hosting.

    Runs ``firebase deploy --only hosting:{target} --project {project_id}``
    via :class:`SafeSubprocessRunner`. The working directory is
    ``<kit_root>/node`` (where ``firebase.json`` lives).

    Args:
        tenant_id: Tenant identifier (validated as kebab-case).
        project_id: Firebase project ID to deploy to.
        hosting_target: Firebase Hosting target name. Defaults to ``tenant_id``.

    Returns:
        Dict with keys:
        - ``success`` (bool): Whether the deploy succeeded.
        - ``url`` (str): Hosting URL (empty on failure).
        - ``deploy_log`` (str): Deploy stdout (or combined stdout+stderr on failure).

    Raises:
        CMSError: With code ``CMS_DEPLOY_FAILED`` if ``firebase`` CLI is not
            found on PATH.
    """
    validate_tenant_id(tenant_id)

    target = hosting_target or tenant_id
    kit_root = get_kit_root()
    cwd = str(kit_root / "node")

    command = [
        "firebase",
        "deploy",
        "--only",
        f"hosting:{target}",
        "--project",
        project_id,
    ]

    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", ""),
    }

    try:
        result = SafeSubprocessRunner.run(
            command,
            cwd=cwd,
            env=env,
            timeout=_DEPLOY_TIMEOUT,
        )
    except FileNotFoundError:
        raise CMSError(
            CMS_DEPLOY_FAILED,
            "firebase CLI not found on PATH. Install firebase-tools: "
            "npm install -g firebase-tools",
            {"tenant_id": tenant_id, "project_id": project_id},
        )

    if result.timed_out:
        return {
            "success": False,
            "url": "",
            "deploy_log": f"Deploy timed out after {_DEPLOY_TIMEOUT}s",
        }

    if result.exit_code != 0:
        combined_log = result.stdout
        if result.stderr:
            combined_log = (
                f"{combined_log}\n{result.stderr}" if combined_log else result.stderr
            )
        return {
            "success": False,
            "url": "",
            "deploy_log": combined_log,
        }

    # Extract hosting URL from output or build default
    url_match = _HOSTING_URL_RE.search(result.stdout)
    url = url_match.group(1) if url_match else f"https://{project_id}.web.app"

    return {
        "success": True,
        "url": url,
        "deploy_log": result.stdout,
    }


def provision_firebase(
    project_id: str,
    display_name: str,
    *,
    region: str = "southamerica-east1",
) -> dict:
    """Provision a new Firebase project with Hosting enabled.

    Runs a sequence of ``gcloud`` commands to:
    1. Create a GCP project
    2. Enable Firebase API
    3. Enable Firestore API
    4. Enable Firebase Hosting API
    5. Add Firebase to the project (via ``firebase`` CLI)

    All commands use Application Default Credentials (ADC).

    Args:
        project_id: GCP project ID to create.
        display_name: Human-readable project name.
        region: GCP region for Firestore/Hosting. Default ``"southamerica-east1"``.

    Returns:
        Dict with keys:
        - ``success`` (bool): Whether all provisioning steps succeeded.
        - ``project_id`` (str): The project ID.
        - ``hosting_url`` (str): Expected hosting URL (empty on failure).

    Raises:
        CMSError: With code ``CMS_PROVISION_FAILED`` if ``gcloud`` CLI is not
            found on PATH.
    """
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", ""),
    }

    commands: list[list[str]] = [
        ["gcloud", "projects", "create", project_id, f"--name={display_name}"],
        [
            "gcloud",
            "services",
            "enable",
            "firebase.googleapis.com",
            f"--project={project_id}",
        ],
        [
            "gcloud",
            "services",
            "enable",
            "firestore.googleapis.com",
            f"--project={project_id}",
        ],
        [
            "gcloud",
            "services",
            "enable",
            "firebasehosting.googleapis.com",
            f"--project={project_id}",
        ],
        [
            "firebase",
            "projects:addFirebase",
            project_id,
        ],
    ]

    for i, command in enumerate(commands):
        try:
            result = SafeSubprocessRunner.run(
                command,
                env=env,
                timeout=_PROVISION_CMD_TIMEOUT,
            )
        except FileNotFoundError:
            cli_name = command[0]  # "gcloud" or "firebase"
            raise CMSError(
                CMS_PROVISION_FAILED,
                f"{cli_name} CLI not found on PATH. "
                f"Install the {'Google Cloud SDK' if cli_name == 'gcloud' else 'firebase-tools'} first.",
                {"project_id": project_id, "command_index": i, "cli": cli_name},
            )

        if result.timed_out:
            return {
                "success": False,
                "project_id": project_id,
                "hosting_url": "",
            }

        if result.exit_code != 0:
            return {
                "success": False,
                "project_id": project_id,
                "hosting_url": "",
            }

    return {
        "success": True,
        "project_id": project_id,
        "hosting_url": f"https://{project_id}.web.app",
    }
