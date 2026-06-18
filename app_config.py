"""Configuration handling for the OCI ARM auto launcher.

Stores all settings (global options + multiple accounts) in a single
config.json file located next to the executable, so the whole folder
stays portable. This module has no third-party dependencies.
"""

from __future__ import annotations

import json
import os
import sys


CONFIG_FILENAME = "config.json"


def get_base_dir() -> str:
    """Folder of the .exe (PyInstaller) or of this source file."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = get_base_dir()
CONFIG_PATH = os.path.join(BASE_DIR, CONFIG_FILENAME)
LOG_FILE = os.path.join(BASE_DIR, "logs", "output.log")



def default_account(name: str = "account-1") -> dict:
    """Return a new account dict with empty/default fields."""
    return {
        "name": name,
        "enabled": True,
        # OCI API credentials
        "region": "ap-chuncheon-1",
        "user_ocid": "",
        "fingerprint": "",
        "tenancy_ocid": "",
        "private_key": "",
        # Instance settings
        "compartment_ocid": "",  # empty -> use tenancy_ocid
        "image_id": "",
        "subnet_id": "",
        "availability_domain": "",
        "ssh_public_key": "",
        "display_name": "big-arm",
        "shape": "VM.Standard.A1.Flex",
        "ocpus": 4,
        "memory_gb": 24,
        "boot_volume_gb": 150,
        "boot_volume_vpus_per_gb": 10,
        "assign_public_ip": True,
    }


def default_config() -> dict:
    """Return a full config with global settings and one empty account."""
    return {
        "request_interval": 1800,
        "max_attempts": 0,
        "discord_webhook_url": "",
        "discord_user_id": "",
        "discord_notify_capacity": True,
        "accounts": [default_account()],
    }



def _coerce_types(config: dict) -> dict:
    """Make sure numeric/boolean fields have the right Python types."""
    int_globals = ["request_interval", "max_attempts"]
    for key in int_globals:
        try:
            config[key] = int(config.get(key, 0) or 0)
        except (TypeError, ValueError):
            config[key] = 0

    config["discord_notify_capacity"] = bool(
        config.get("discord_notify_capacity", True)
    )

    int_account = [
        "ocpus",
        "memory_gb",
        "boot_volume_gb",
        "boot_volume_vpus_per_gb",
    ]
    for account in config.get("accounts", []):
        for key in int_account:
            try:
                account[key] = int(account.get(key, 0) or 0)
            except (TypeError, ValueError):
                account[key] = 0
        account["enabled"] = bool(account.get("enabled", True))
        account["assign_public_ip"] = bool(account.get("assign_public_ip", True))

    return config


def normalize_config(config: dict) -> dict:
    """Fill missing keys using defaults and coerce types."""
    base = default_config()
    base.pop("accounts", None)

    merged = {**base, **{k: v for k, v in config.items() if k != "accounts"}}

    accounts = config.get("accounts") or []
    if not accounts:
        accounts = [default_account()]

    normalized_accounts = []
    for index, account in enumerate(accounts):
        template = default_account(f"account-{index + 1}")
        normalized_accounts.append({**template, **(account or {})})

    merged["accounts"] = normalized_accounts
    return _coerce_types(merged)



def load_config(path: str = CONFIG_PATH) -> dict:
    """Load config.json, or return a default config if it does not exist."""
    if not os.path.exists(path):
        return normalize_config(default_config())

    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    return normalize_config(data)


def save_config(config: dict, path: str = CONFIG_PATH) -> None:
    """Write config to config.json (pretty-printed, UTF-8)."""
    normalized = normalize_config(config)

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(normalized, file, indent=2, ensure_ascii=False)


def effective_compartment(account: dict) -> str:
    """Compartment OCID, falling back to the tenancy OCID when empty."""
    return account.get("compartment_ocid") or account.get("tenancy_ocid", "")

