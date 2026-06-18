"""Tkinter GUI for the OCI ARM auto launcher.

One window to enter all settings: global options plus one tab per account.
Save/Load config.json, Start/Stop the launcher, and watch a live log.

Tkinter ships with standard Python, so no extra install (and no Docker /
Hyper-V) is needed.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

import app_config
import launcher_core


# Per-account text fields shown in each account tab: (config key, label).
ACCOUNT_FIELDS = [
    ("name", "Account name (any label, shown in logs)"),
    ("region", "Region (select from list)"),
    ("user_ocid", "User OCID"),
    ("fingerprint", "API key fingerprint"),
    ("tenancy_ocid", "Tenancy OCID"),
    ("compartment_ocid", "Compartment OCID (blank = tenancy)"),
    ("image_id", "Image OCID"),
    ("subnet_id", "Subnet OCID"),
    ("availability_domain", "Availability domain"),
    ("display_name", "Instance display name"),
    ("shape", "Shape (select or type; default VM.Standard.A1.Flex)"),
]

# Numeric account fields: (config key, label).
ACCOUNT_NUMBERS = [
    ("ocpus", "OCPUs"),
    ("memory_gb", "Memory (GB)"),
    ("boot_volume_gb", "Boot volume (GB)"),
    ("boot_volume_vpus_per_gb", "Boot VPUs/GB"),
]

# OCI commercial regions (Korea first). Shown in the Region dropdown.
REGIONS = [
    "ap-chuncheon-1",
    "ap-seoul-1",
    "ap-tokyo-1",
    "ap-osaka-1",
    "ap-singapore-1",
    "ap-singapore-2",
    "ap-mumbai-1",
    "ap-hyderabad-1",
    "ap-sydney-1",
    "ap-melbourne-1",
    "us-ashburn-1",
    "us-phoenix-1",
    "us-sanjose-1",
    "us-chicago-1",
    "ca-toronto-1",
    "ca-montreal-1",
    "sa-saopaulo-1",
    "sa-vinhedo-1",
    "sa-santiago-1",
    "sa-bogota-1",
    "uk-london-1",
    "uk-cardiff-1",
    "eu-frankfurt-1",
    "eu-amsterdam-1",
    "eu-zurich-1",
    "eu-madrid-1",
    "eu-milan-1",
    "eu-paris-1",
    "eu-marseille-1",
    "eu-stockholm-1",
    "me-jeddah-1",
    "me-dubai-1",
    "me-abudhabi-1",
    "il-jerusalem-1",
    "af-johannesburg-1",
    "mx-queretaro-1",
    "mx-monterrey-1",
]

# Common OCI shapes for the (editable) Shape dropdown. You can still type any
# other shape name directly; this list is only a convenience.
SHAPES = [
    "VM.Standard.A1.Flex",
    "VM.Standard.E2.1.Micro",
    "VM.Standard.E3.Flex",
    "VM.Standard.E4.Flex",
    "VM.Standard.E5.Flex",
    "VM.Standard3.Flex",
    "VM.Optimized3.Flex",
]



def _is_int(text: str) -> bool:
    try:
        int(str(text).strip())
        return True
    except (TypeError, ValueError):
        return False


class AccountTab:
    """Widgets for editing a single account inside a notebook tab."""

    def __init__(self, parent: ttk.Frame):
        self.frame = parent
        self.text_vars: dict[str, tk.StringVar] = {}
        self.number_vars: dict[str, tk.StringVar] = {}
        self.enabled_var = tk.BooleanVar(value=True)
        self.public_ip_var = tk.BooleanVar(value=True)

        row = 0
        check_row = ttk.Frame(parent)
        check_row.grid(row=row, column=0, columnspan=2, sticky="w", padx=6, pady=(6, 0))
        ttk.Checkbutton(
            check_row, text="Enabled", variable=self.enabled_var
        ).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(
            check_row, text="Assign public IP", variable=self.public_ip_var
        ).pack(side="left")
        row += 1

        hint = (
            "Enabled: 체크하면 이 계정으로 시도, 해제하면 건너뜀   |   "
            "Assign public IP: 인스턴스에 공인 IP 부여(SSH 접속용, 보통 켜둠)"
        )
        ttk.Label(parent, text=hint, foreground="gray").grid(
            row=row, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 6)
        )
        row += 1

        for key, label in ACCOUNT_FIELDS:
            ttk.Label(parent, text=label).grid(
                row=row, column=0, sticky="w", padx=6, pady=2
            )
            var = tk.StringVar()
            self.text_vars[key] = var
            if key == "region":
                widget = ttk.Combobox(
                    parent,
                    textvariable=var,
                    values=REGIONS,
                    state="readonly",
                    width=57,
                )
            elif key == "shape":
                # Editable: pick a common shape or type any other.
                widget = ttk.Combobox(
                    parent,
                    textvariable=var,
                    values=SHAPES,
                    width=57,
                )
            else:
                widget = ttk.Entry(parent, textvariable=var, width=60)
            widget.grid(row=row, column=1, sticky="we", padx=6, pady=2)
            row += 1

        num_frame = ttk.Frame(parent)
        num_frame.grid(row=row, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        for index, (key, label) in enumerate(ACCOUNT_NUMBERS):
            ttk.Label(num_frame, text=label).grid(row=0, column=index * 2, padx=4)
            var = tk.StringVar()
            self.number_vars[key] = var
            ttk.Entry(num_frame, textvariable=var, width=8).grid(
                row=0, column=index * 2 + 1, padx=4
            )
        row += 1

        self._build_text_areas(parent, row)
        parent.columnconfigure(1, weight=1)



    def _build_text_areas(self, parent: ttk.Frame, start_row: int) -> None:
        ttk.Label(
            parent,
            text="API private key (PEM): -----BEGIN PRIVATE KEY----- 와 "
            "-----END PRIVATE KEY----- 줄까지 통째로 붙여넣으세요",
        ).grid(
            row=start_row, column=0, columnspan=2, sticky="w", padx=6, pady=(8, 0)
        )
        self.private_key_text = scrolledtext.ScrolledText(
            parent, height=6, width=70, wrap="none"
        )
        self.private_key_text.grid(
            row=start_row + 1, column=0, columnspan=2, sticky="we", padx=6, pady=2
        )

        ttk.Label(parent, text="SSH public key (ssh-rsa ... / ssh-ed25519 ...)").grid(
            row=start_row + 2, column=0, columnspan=2, sticky="w", padx=6, pady=(8, 0)
        )
        self.ssh_text = scrolledtext.ScrolledText(
            parent, height=3, width=70, wrap="none"
        )
        self.ssh_text.grid(
            row=start_row + 3, column=0, columnspan=2, sticky="we", padx=6, pady=2
        )

    def load(self, account: dict) -> None:
        self.enabled_var.set(bool(account.get("enabled", True)))
        self.public_ip_var.set(bool(account.get("assign_public_ip", True)))
        for key, var in self.text_vars.items():
            var.set(str(account.get(key, "")))
        for key, var in self.number_vars.items():
            var.set(str(account.get(key, "")))
        self.private_key_text.delete("1.0", tk.END)
        self.private_key_text.insert("1.0", account.get("private_key", ""))
        self.ssh_text.delete("1.0", tk.END)
        self.ssh_text.insert("1.0", account.get("ssh_public_key", ""))

    def dump(self) -> dict:
        account = {
            "enabled": self.enabled_var.get(),
            "assign_public_ip": self.public_ip_var.get(),
            "private_key": self.private_key_text.get("1.0", tk.END).strip(),
            "ssh_public_key": self.ssh_text.get("1.0", tk.END).strip(),
        }
        for key, var in self.text_vars.items():
            account[key] = var.get().strip()
        for key, var in self.number_vars.items():
            account[key] = var.get().strip()
        return account



class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("OCI ARM Auto Launcher")
        self.root.geometry("780x820")

        self.log_queue: "queue.Queue[str]" = queue.Queue()
        self.stop_event: threading.Event | None = None
        self.worker: threading.Thread | None = None
        self.account_tabs: list[AccountTab] = []

        self.request_interval = tk.StringVar()
        self.max_attempts = tk.StringVar()
        self.discord_webhook_url = tk.StringVar()
        self.discord_user_id = tk.StringVar()
        self.discord_notify_capacity = tk.BooleanVar(value=True)

        self._build_global(root)
        self._build_accounts(root)
        self._build_controls(root)
        self._build_log(root)

        self._load_initial()
        self.root.after(200, self._poll_log)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_global(self, root: tk.Tk) -> None:
        frame = ttk.LabelFrame(root, text="Global settings")
        frame.pack(fill="x", padx=8, pady=6)

        ttk.Label(frame, text="Retry interval (sec)").grid(
            row=0, column=0, sticky="w", padx=6, pady=4
        )
        ttk.Entry(frame, textvariable=self.request_interval, width=10).grid(
            row=0, column=1, sticky="w", padx=6
        )
        ttk.Label(frame, text="Max attempts (0 = unlimited)").grid(
            row=0, column=2, sticky="w", padx=6
        )
        ttk.Entry(frame, textvariable=self.max_attempts, width=10).grid(
            row=0, column=3, sticky="w", padx=6
        )

        ttk.Label(frame, text="Discord webhook URL").grid(
            row=1, column=0, sticky="w", padx=6, pady=4
        )
        ttk.Entry(frame, textvariable=self.discord_webhook_url, width=60).grid(
            row=1, column=1, columnspan=3, sticky="we", padx=6
        )

        ttk.Label(frame, text="Discord user ID").grid(
            row=2, column=0, sticky="w", padx=6, pady=4
        )
        ttk.Entry(frame, textvariable=self.discord_user_id, width=30).grid(
            row=2, column=1, sticky="w", padx=6
        )
        ttk.Checkbutton(
            frame, text="Notify on capacity", variable=self.discord_notify_capacity
        ).grid(row=2, column=2, columnspan=2, sticky="w", padx=6)
        frame.columnconfigure(1, weight=1)



    def _build_accounts(self, root: tk.Tk) -> None:
        frame = ttk.LabelFrame(root, text="Accounts")
        frame.pack(fill="both", expand=True, padx=8, pady=6)

        button_row = ttk.Frame(frame)
        button_row.pack(fill="x", padx=4, pady=4)
        ttk.Button(button_row, text="+ Add account", command=self.add_account).pack(
            side="left"
        )
        ttk.Button(
            button_row, text="- Remove current", command=self.remove_account
        ).pack(side="left", padx=6)

        self.notebook = ttk.Notebook(frame)
        self.notebook.pack(fill="both", expand=True, padx=4, pady=4)

    def _make_scrollable(self, parent: ttk.Frame) -> ttk.Frame:
        """Wrap a tab in a vertical scroll area and return the inner frame."""
        canvas = tk.Canvas(parent, borderwidth=0, highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner_config(_event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_config(event):
            canvas.itemconfigure(window, width=event.width)

        inner.bind("<Configure>", _on_inner_config)
        canvas.bind("<Configure>", _on_canvas_config)

        def _on_wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _on_wheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

        return inner

    def add_account(self, account: dict | None = None) -> AccountTab:
        index = len(self.account_tabs) + 1
        tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(tab_frame, text=f"Account {index}")
        inner = self._make_scrollable(tab_frame)
        tab = AccountTab(inner)
        tab.load(account or app_config.default_account(f"account-{index}"))
        self.account_tabs.append(tab)
        self.notebook.select(len(self.account_tabs) - 1)
        return tab

    def remove_account(self) -> None:
        if len(self.account_tabs) <= 1:
            messagebox.showinfo("Accounts", "At least one account is required.")
            return
        current = self.notebook.index(self.notebook.select())
        self.notebook.forget(current)
        self.account_tabs.pop(current)
        for i in range(len(self.account_tabs)):
            self.notebook.tab(i, text=f"Account {i + 1}")



    def _build_controls(self, root: tk.Tk) -> None:
        frame = ttk.Frame(root)
        frame.pack(fill="x", padx=8, pady=4)

        ttk.Button(frame, text="Save config", command=self.save).pack(side="left")
        ttk.Button(frame, text="Reload config", command=self.load).pack(
            side="left", padx=6
        )
        self.start_button = ttk.Button(frame, text="Start", command=self.start)
        self.start_button.pack(side="left", padx=(24, 6))
        self.stop_button = ttk.Button(
            frame, text="Stop", command=self.stop, state="disabled"
        )
        self.stop_button.pack(side="left")

        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(frame, textvariable=self.status_var).pack(side="right", padx=6)

    def _build_log(self, root: tk.Tk) -> None:
        frame = ttk.LabelFrame(root, text="Log")
        frame.pack(fill="both", expand=True, padx=8, pady=6)
        self.log_widget = scrolledtext.ScrolledText(
            frame, height=12, state="disabled", wrap="word"
        )
        self.log_widget.pack(fill="both", expand=True, padx=4, pady=4)



    def collect_config(self) -> dict:
        return {
            "request_interval": self.request_interval.get().strip() or "0",
            "max_attempts": self.max_attempts.get().strip() or "0",
            "discord_webhook_url": self.discord_webhook_url.get().strip(),
            "discord_user_id": self.discord_user_id.get().strip(),
            "discord_notify_capacity": self.discord_notify_capacity.get(),
            "accounts": [tab.dump() for tab in self.account_tabs],
        }

    def _validate_config(self, config: dict) -> list[str]:
        """Return a list of human-readable problems (empty list = OK)."""
        errors: list[str] = []

        for key, label in [
            ("request_interval", "Retry interval (sec)"),
            ("max_attempts", "Max attempts"),
        ]:
            value = str(config.get(key, "")).strip()
            if value and not _is_int(value):
                errors.append(f"Global '{label}' must be a whole number (got '{value}').")

        names: list[str] = []
        for i, account in enumerate(config.get("accounts", []), start=1):
            name = str(account.get("name", "")).strip()
            label_name = name or f"Account {i}"
            if not name:
                errors.append(f"Account {i}: name is empty.")
            else:
                names.append(name)

            for key, label in [
                ("ocpus", "OCPUs"),
                ("memory_gb", "Memory (GB)"),
                ("boot_volume_gb", "Boot volume (GB)"),
                ("boot_volume_vpus_per_gb", "Boot VPUs/GB"),
            ]:
                value = str(account.get(key, "")).strip()
                if value and not _is_int(value):
                    errors.append(
                        f"[{label_name}] '{label}' must be a whole number (got '{value}')."
                    )

        seen: set[str] = set()
        dups: set[str] = set()
        for name in names:
            if name in seen:
                dups.add(name)
            seen.add(name)
        if dups:
            errors.append(
                "Duplicate account names: "
                + ", ".join(sorted(dups))
                + ". Each account name must be unique."
            )

        return errors

    def apply_config(self, config: dict) -> None:
        config = app_config.normalize_config(config)
        self.request_interval.set(str(config["request_interval"]))
        self.max_attempts.set(str(config["max_attempts"]))
        self.discord_webhook_url.set(config["discord_webhook_url"])
        self.discord_user_id.set(config["discord_user_id"])
        self.discord_notify_capacity.set(config["discord_notify_capacity"])

        for tab_id in self.notebook.tabs():
            self.notebook.forget(tab_id)
        self.account_tabs.clear()
        for account in config["accounts"]:
            self.add_account(account)
        if self.account_tabs:
            self.notebook.select(0)

    def _load_initial(self) -> None:
        import os

        if os.path.exists(app_config.CONFIG_PATH):
            self.apply_config(app_config.load_config())
        else:
            self.apply_config(app_config.default_config())

    def save(self) -> None:
        config = self.collect_config()
        errors = self._validate_config(config)
        if errors:
            messagebox.showerror("Cannot save", "\n".join(errors))
            return
        try:
            app_config.save_config(config)
            self._append_log(f"Saved config to {app_config.CONFIG_PATH}")
            messagebox.showinfo("Saved", "Configuration saved to config.json.")
        except Exception as error:
            messagebox.showerror("Save failed", str(error))

    def load(self) -> None:
        try:
            self.apply_config(app_config.load_config())
            self._append_log("Reloaded config from config.json")
        except Exception as error:
            messagebox.showerror("Load failed", str(error))



    _DONE_MARKER = "<<<LAUNCHER_DONE>>>"

    def start(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            return

        config = self.collect_config()
        errors = self._validate_config(config)
        if errors:
            messagebox.showerror("Cannot start", "\n".join(errors))
            return

        try:
            app_config.save_config(config)
        except Exception as error:
            messagebox.showerror("Save failed", str(error))
            return

        enabled = [a for a in config["accounts"] if a.get("enabled", True)]
        if not enabled:
            messagebox.showwarning("Start", "No enabled accounts to run.")
            return

        self.stop_event = threading.Event()
        log = launcher_core.make_logger(self.log_queue.put)

        def worker() -> None:
            try:
                launcher_core.run_loop(config, log=log, stop_event=self.stop_event)
            except Exception as error:
                log(f"Fatal error in launcher: {error}")
            finally:
                self.log_queue.put(self._DONE_MARKER)

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.status_var.set("Running")

    def stop(self) -> None:
        if self.stop_event is not None:
            self.stop_event.set()
            self.status_var.set("Stopping...")
            self._append_log("Stop requested; will stop shortly.")



    def _append_log(self, line: str) -> None:
        self.log_widget.config(state="normal")
        self.log_widget.insert(tk.END, line + "\n")
        self.log_widget.see(tk.END)
        self.log_widget.config(state="disabled")

    def _poll_log(self) -> None:
        try:
            while True:
                line = self.log_queue.get_nowait()
                if line == self._DONE_MARKER:
                    self.start_button.config(state="normal")
                    self.stop_button.config(state="disabled")
                    self.status_var.set("Idle")
                else:
                    self._append_log(line)
        except queue.Empty:
            pass
        self.root.after(200, self._poll_log)

    def _on_close(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            if not messagebox.askyesno(
                "Quit", "The launcher is still running. Stop and quit?"
            ):
                return
            if self.stop_event is not None:
                self.stop_event.set()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
