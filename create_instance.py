"""Headless CLI runner for the OCI ARM auto launcher.

Loads config.json (next to the executable) and tries to launch an ARM
instance for every enabled account, retrying until each one succeeds.

If config.json does not exist yet, a template is created so you can edit
it (or use the GUI) and run again.

Usage:
    python create_instance.py [--config PATH]
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


def main() -> None:
    parser = argparse.ArgumentParser(description="OCI ARM auto launcher (CLI)")
    parser.add_argument(
        "--config",
        default=app_config.CONFIG_PATH,
        help="Path to config.json (default: next to the executable)",
    )
    args = parser.parse_args()

    log = launcher_core.make_logger()
    config = load_or_create(args.config, log)

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
