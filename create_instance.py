"""Headless CLI runner for the OCI ARM auto launcher.

Loads config.json (next to the executable) and tries to launch an ARM
instance for every enabled account, retrying until each one succeeds.

If config.json does not exist yet, a template is created so you can edit
it (or use the GUI) and run again.

Secrets handling (for CI / GitHub Actions):
    The Discord webhook URL and user ID can be supplied via environment
    variables instead of being stored in config.json. When set, these
    environment variables take priority over the values in config.json:

        DISCORD_WEBHOOK_URL
        DISCORD_USER_ID

Usage:
    python create_instance.py [--config PATH] [--once]

    --once   Run a single launch cycle (try each enabled account once) and
             exit. Intended for scheduled GitHub Actions runs, where the
             workflow itself provides the retry cadence (e.g. every 6 hours)
             instead of an in-process sleep loop.
"""

from __future__ import annotations

import argparse
import os
import sys

import app_config
import launcher_core


def load_or_create(config_path: str, log) -> dict:
    if os.path.exists(config_path):
        return app_config.load_config(config_path)

    log(
        f"No config found at {config_path}. A template was created; "
        "edit it (or use the GUI) and run again."
    )
    app_config.save_config(app_config.default_config(), config_path)
    return app_config.load_config(config_path)


def apply_secret_overrides(config: dict, log) -> dict:
    """Override Discord settings from environment variables when present.

    Lets sensitive values be injected from GitHub Secrets at runtime instead
    of being committed in config.json. The values themselves are never logged.
    """
    webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    if webhook is not None and webhook.strip():
        config["discord_webhook_url"] = webhook.strip()
        log("Discord webhook URL loaded from environment.")

    user_id = os.environ.get("DISCORD_USER_ID")
    if user_id is not None and user_id.strip():
        config["discord_user_id"] = user_id.strip()
        log("Discord user ID loaded from environment.")

    return config


def main() -> None:
    parser = argparse.ArgumentParser(description="OCI ARM auto launcher (CLI)")
    parser.add_argument(
        "--config",
        default=app_config.CONFIG_PATH,
        help="Path to config.json (default: next to the executable)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single launch cycle and exit (for scheduled CI runs).",
    )
    args = parser.parse_args()

    log = launcher_core.make_logger()
    config = load_or_create(args.config, log)
    config = apply_secret_overrides(config, log)

    if args.once:
        # One cycle only: the workflow schedule provides the retry cadence.
        config["max_attempts"] = 1

    enabled = [a for a in config.get("accounts", []) if a.get("enabled", True)]
    if not enabled:
        log("No enabled accounts in config. Nothing to do. Exiting.")
        return

    try:
        launcher_core.run_loop(config, log=log)
    except KeyboardInterrupt:
        log("Interrupted by user. Exiting.")
        sys.exit(0)


if __name__ == "__main__":
    main()
