"""Core launch logic for the OCI ARM auto launcher.

Builds an OCI Compute client per account (using an inline private key),
tries to launch an instance, and runs a loop over multiple accounts until
each one succeeds (or max attempts is reached).
"""

from __future__ import annotations

import os
import sys
import time
import traceback
from datetime import datetime, timezone

import oci
from oci.core.models import (
    CreateVnicDetails,
    InstanceSourceViaImageDetails,
    LaunchInstanceDetails,
    LaunchInstanceShapeConfigDetails,
)

import app_config


def now_text() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


# Rotate logs/output.log once it grows past this size, keeping one backup
# (output.log.1). Keeps the log from growing forever during long retry runs.
MAX_LOG_BYTES = 2_000_000


def make_logger(extra_sink=None):
    """Create a log function that writes to console, file, and an optional sink.

    `extra_sink` is a callable taking one string (used by the GUI to display
    log lines in real time).
    """
    os.makedirs(os.path.dirname(app_config.LOG_FILE), exist_ok=True)

    def _rotate_if_needed() -> None:
        try:
            if (
                os.path.exists(app_config.LOG_FILE)
                and os.path.getsize(app_config.LOG_FILE) > MAX_LOG_BYTES
            ):
                backup = app_config.LOG_FILE + ".1"
                if os.path.exists(backup):
                    os.remove(backup)
                os.replace(app_config.LOG_FILE, backup)
        except OSError:
            pass

    def log(message: str) -> None:
        line = f"[{now_text()}] {message}"

        # Always deliver to the GUI sink and file first. In a PyInstaller
        # --windowed build sys.stdout/stderr are None, so print() would
        # raise; guard it so logging never crashes the worker.
        if extra_sink is not None:
            try:
                extra_sink(line)
            except Exception:
                pass

        try:
            _rotate_if_needed()
            with open(app_config.LOG_FILE, "a", encoding="utf-8") as file:
                file.write(line + "\n")
        except OSError:
            pass

        try:
            if sys.stdout is not None:
                print(line, flush=True)
        except Exception:
            pass

    return log


def send_discord(config: dict, message: str, log) -> None:
    url = config.get("discord_webhook_url", "")
    if not url:
        return
    try:
        import requests

        response = requests.post(url, json={"content": message}, timeout=15)
        response.raise_for_status()
    except Exception as error:
        log(f"Discord notification failed: {error}")


def is_capacity_error(text: str) -> bool:
    lowered = text.lower()
    return any(
        keyword in lowered
        for keyword in ("out of host capacity", "out of capacity", "capacity")
    )



def validate_ssh_public_key(public_key: str, log) -> str:
    public_key = (public_key or "").strip()

    if not public_key:
        raise RuntimeError("SSH public key is empty.")

    if "BEGIN PRIVATE KEY" in public_key or "BEGIN RSA PRIVATE KEY" in public_key:
        raise RuntimeError(
            "SSH public key looks like a private key. Use a public key such "
            "as 'ssh-rsa ...' or 'ssh-ed25519 ...'."
        )

    if not (
        public_key.startswith("ssh-rsa ")
        or public_key.startswith("ssh-ed25519 ")
        or public_key.startswith("ecdsa-sha2-")
    ):
        log(
            "Warning: SSH public key does not start with ssh-rsa, ssh-ed25519, "
            "or ecdsa-sha2-. Please check the key format."
        )

    return public_key


def build_compute_client(account: dict):
    """Create a ComputeClient for an account using its inline private key.

    Instead of constructing a Signer manually (which oci.config.validate_config
    does not recognize), we build a full config dict and pass the private key
    inline via "key_content". The SDK treats key_content as a fallback for
    key content, so no key file on disk is needed.
    """
    private_key = (account.get("private_key") or "").strip()
    if "BEGIN" not in private_key or "PRIVATE KEY" not in private_key:
        raise RuntimeError(
            "API private key must include the -----BEGIN PRIVATE KEY----- and "
            "-----END PRIVATE KEY----- lines. Paste the full key file content."
        )

    config = {
        "user": account["user_ocid"],
        "fingerprint": account["fingerprint"],
        "tenancy": account["tenancy_ocid"],
        "region": account["region"],
        "key_content": private_key,
    }

    try:
        oci.config.validate_config(config)
    except oci.exceptions.InvalidConfig as error:
        detail = error.args[0] if error.args else {}
        if isinstance(detail, dict):
            problems = ", ".join(f"{key}: {why}" for key, why in detail.items())
        else:
            problems = str(error)
        raise RuntimeError(f"Invalid OCI credentials ({problems})")

    return oci.core.ComputeClient(config)



def build_launch_details(account: dict, ssh_public_key: str) -> LaunchInstanceDetails:
    source_details = InstanceSourceViaImageDetails(
        source_type="image",
        image_id=account["image_id"],
        boot_volume_size_in_gbs=account["boot_volume_gb"],
        boot_volume_vpus_per_gb=account["boot_volume_vpus_per_gb"],
    )

    shape_config = LaunchInstanceShapeConfigDetails(
        ocpus=account["ocpus"],
        memory_in_gbs=account["memory_gb"],
    )

    vnic_details = CreateVnicDetails(
        subnet_id=account["subnet_id"],
        assign_public_ip=account["assign_public_ip"],
        assign_private_dns_record=True,
    )

    return LaunchInstanceDetails(
        availability_domain=account["availability_domain"],
        compartment_id=app_config.effective_compartment(account),
        display_name=account["display_name"],
        shape=account["shape"],
        shape_config=shape_config,
        source_details=source_details,
        create_vnic_details=vnic_details,
        metadata={"ssh_authorized_keys": ssh_public_key},
        is_pv_encryption_in_transit_enabled=True,
    )



def _mention(config: dict) -> str:
    user_id = config.get("discord_user_id", "")
    return f"<@{user_id}> " if user_id else ""


def attempt_once(account, client, launch_details, config, log) -> str:
    """Try to launch once. Returns 'success', 'capacity', or 'error'."""
    name = account["name"]
    try:
        response = client.launch_instance(launch_details)
        instance = response.data
        message = (
            f"{_mention(config)}**Success [{name}]:** Instance "
            f"`{account['display_name']}` launched.\n"
            f"Instance ID: `{instance.id}`\n"
            f"Lifecycle state: `{instance.lifecycle_state}`"
        )
        log(message)
        send_discord(config, message, log)
        return "success"

    except oci.exceptions.ServiceError as error:
        error_text = str(error)
        capacity = is_capacity_error(error_text)
        if capacity:
            message = (
                f"**Capacity [{name}]:** Out of host capacity for "
                f"`{account['display_name']}`."
            )
            log(message)
            if config.get("discord_notify_capacity", True):
                send_discord(config, message, log)
        else:
            message = (
                f"{_mention(config)}**Error [{name}]:** "
                f"Status `{error.status}`, Code `{error.code}`: {error.message}"
            )
            log(message)
            log(error_text)
            send_discord(config, message, log)
        return "capacity" if capacity else "error"

    except Exception as error:
        log(f"{_mention(config)}**Fatal [{name}]:** {error}")
        log(traceback.format_exc())
        send_discord(config, f"{_mention(config)}**Fatal [{name}]:** {error}", log)
        return "error"



def _prepare_account(account: dict, log):
    """Validate and build client + launch details for one account.

    Returns (client, launch_details) or None if preparation failed.
    """
    name = account["name"]
    required = ["user_ocid", "fingerprint", "tenancy_ocid", "private_key",
                "image_id", "subnet_id", "availability_domain"]
    missing = [key for key in required if not str(account.get(key, "")).strip()]
    if missing:
        log(f"Skip [{name}]: missing required fields: {', '.join(missing)}")
        return None

    try:
        ssh_key = validate_ssh_public_key(account.get("ssh_public_key", ""), log)
        client = build_compute_client(account)
        launch_details = build_launch_details(account, ssh_key)
        return client, launch_details
    except Exception as error:
        log(f"Skip [{name}]: setup failed: {error}")
        return None


def _sleep_interruptible(seconds: int, stop_event) -> None:
    end = time.monotonic() + max(0, seconds)
    while time.monotonic() < end:
        if stop_event is not None and stop_event.is_set():
            return
        time.sleep(min(1.0, end - time.monotonic()))



def run_loop(config: dict, log=None, stop_event=None) -> None:
    """Run the launch loop over all enabled accounts until each succeeds.

    `log` is a log function (use make_logger()); if None, one is created.
    `stop_event` is an optional threading.Event used to stop early.
    """
    if log is None:
        log = make_logger()

    config = app_config.normalize_config(config)
    interval = config["request_interval"]
    max_attempts = config["max_attempts"]

    enabled = [a for a in config["accounts"] if a.get("enabled", True)]
    if not enabled:
        log("No enabled accounts. Nothing to do.")
        return

    log(f"Launcher started for {len(enabled)} account(s).")
    log(f"Interval: {interval}s, Max attempts: {max_attempts or 'unlimited'}")

    prepared = {}
    for account in enabled:
        result = _prepare_account(account, log)
        if result is not None:
            prepared[account["name"]] = (account, *result)

    if not prepared:
        log("No account is ready to launch. Check the settings.")
        return

    done = set()
    cycle = 0

    while True:
        if stop_event is not None and stop_event.is_set():
            log("Stop requested. Exiting.")
            return

        cycle += 1
        for name, (account, client, launch_details) in prepared.items():
            if name in done:
                continue
            if stop_event is not None and stop_event.is_set():
                log("Stop requested. Exiting.")
                return

            log(f"Cycle #{cycle} - attempting [{name}]...")
            status = attempt_once(account, client, launch_details, config, log)
            if status == "success":
                done.add(name)

        if len(done) >= len(prepared):
            log("All accounts launched successfully. Done.")
            return

        if max_attempts > 0 and cycle >= max_attempts:
            log(f"MAX_ATTEMPTS reached ({max_attempts}). Exiting.")
            return

        remaining = len(prepared) - len(done)
        log(f"{remaining} account(s) pending. Sleeping {interval}s...")
        _sleep_interruptible(interval, stop_event)
