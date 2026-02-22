import asyncio
import os
import subprocess
import zipfile
import shutil
import tempfile
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, SelectionList, Label, Static, Button, ProgressBar, RichLog, Input, DataTable
from textual.containers import Vertical, Horizontal, ScrollableContainer, Container
from textual.binding import Binding
from textual.screen import ModalScreen

# --- PERSISTENCE CONFIG ---
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
REGISTRY_PATH = os.path.join(BASE_PATH, "registry.json")
HISTORY_PATH = os.path.join(BASE_PATH, "history.json")
APK_DIR = os.path.join(BASE_PATH, "apks")

if not os.path.exists(APK_DIR):
    os.makedirs(APK_DIR)

def load_json(path: str, default: Any) -> Any:
    if os.path.exists(path):
        with open(path, 'r') as f:
            try: return json.load(f)
            except: return default
    return default

def save_json(path: str, data: Any):
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)

# --- MODALS ---

class PackageBrowserModal(ModalScreen):
    """Searchable list of installed apps on a device."""
    BINDINGS = [Binding("escape", "dismiss(None)", "Back")]

    def __init__(self, packages: List[str], nickname: str):
        super().__init__()
        self.packages = sorted(packages)
        self.nickname = nickname

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(f"[b]Apps on {self.nickname}[/b]\nSelect packages to uninstall:"),
            Input(placeholder="Search packages (e.g. com.google...)", id="pkg-search"),
            SelectionList(id="pkg-browser-list"),
            Horizontal(
                Button("Uninstall Selected", variant="error", id="btn-confirm"),
                Button("Back (Esc)", variant="default", id="btn-cancel"),
            ),
            id="modal-container"
        )

    def on_mount(self) -> None:
        self.update_list("")

    def on_input_changed(self, event: Input.Changed) -> None:
        self.update_list(event.value.lower())

    def update_list(self, filter_text: str) -> None:
        list_widget = self.query_one("#pkg-browser-list", SelectionList)
        list_widget.clear_options()
        options = [(pkg, pkg) for pkg in self.packages if filter_text in pkg.lower()]
        list_widget.add_options(options)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-confirm":
            self.dismiss(self.query_one("#pkg-browser-list").selected)
        else:
            self.dismiss(None)

class PairModal(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss(None)", "Back")]
    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("[b]Wireless Pairing[/b]\nEnter IP:Port and 6-digit Code"),
            Input(placeholder="192.168.1.50:34567", id="pair-address"),
            Input(placeholder="6-digit Code", id="pair-code"),
            Horizontal(
                Button("Pair", variant="success", id="btn-pair"),
                Button("Back", variant="error", id="btn-cancel"),
            ),
            id="modal-container"
        )
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-pair":
            self.dismiss({"address": self.query_one("#pair-address").value, "code": self.query_one("#pair-code").value})
        else: self.dismiss(None)

class ConnectModal(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss(None)", "Back")]
    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("[b]Wireless Connect[/b]\nEnter IP:Port from Wireless Debugging screen"),
            Input(placeholder="192.168.1.50:5555", id="ip-input"),
            Horizontal(
                Button("Connect", variant="success", id="connect"),
                Button("Back", variant="error", id="cancel"),
            ),
            id="modal-container"
        )
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "connect":
            self.dismiss(self.query_one("#ip-input").value)
        else: self.dismiss(None)

# --- TASK COMPONENT ---

class InstallTask(Static):
    def __init__(self, device_id: str, nickname: str, apk_name: str):
        super().__init__()
        self.device_id = device_id
        self.nickname = nickname
        self.apk_name = apk_name

    def compose(self) -> ComposeResult:
        with Horizontal(classes="task-row"):
            yield Label(f"📱 {self.nickname}", classes="task-label")
            yield Label(f"📦 {self.apk_name[:12]}", classes="task-label")
            yield ProgressBar(total=100, show_eta=False, id="pbar")
            yield Label("Pending", id="status-text")

    def update_status(self, message: str, progress: Optional[float] = None):
        if progress is not None: self.query_one(ProgressBar).update(progress=progress)
        self.query_one("#status-text").update(message)

# --- MAIN APP ---

class AdvancedAdbManager(App):
    TITLE = "ADB COMMAND CENTER v4"
    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("i", "install", "Install"),
        Binding("l", "list_packages", "List Apps"),
        Binding("h", "toggle_history", "History/Live"),
        Binding("w", "wireless_connect", "Connect"),
        Binding("p", "wireless_pair", "Pair"),
        Binding("k", "kill_adb", "Reset ADB"),
        Binding("q", "quit", "Quit"),
    ]

    CSS = """
    Screen { background: #1a1b26; }
    #app-grid { layout: horizontal; height: 100%; width: 100%; }
    #side-bar { width: 42; height: 100%; background: #24283b; border-right: tall #414868; padding: 1; }
    #main-zone { width: 1fr; height: 100%; padding: 1; }
    SelectionList { height: 1fr; border: solid #414868; background: #16161e; margin-bottom: 1; }
    #tasks-container { height: 1fr; border: solid #414868; background: #1a1b26; margin-bottom: 1; padding: 1; }
    #history-table { height: 1fr; display: none; border: solid #414868; background: #1a1b26; margin-bottom: 1; }
    #debug-log { height: 10; border: double #414868; background: #16161e; color: #c0caf5; }
    .task-row { height: 3; margin-bottom: 1; background: #292e42; border: round #414868; padding: 0 1; align: center middle; }
    .task-label { width: 12; margin-right: 1; text-style: bold; color: #bb9af7; }
    #status-text { width: 12; margin-left: 1; color: #7aa2f7; }
    Button { width: 100%; margin-top: 1; }
    #modal-container { width: 60; height: auto; background: #24283b; border: thick #7aa2f7; padding: 1 2; align: center middle; }
    Input { margin: 1 0; border: inner #414868; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="app-grid"):
            with Vertical(id="side-bar"):
                yield Label("[b]📱 DEVICE REGISTRY[/b]")
                yield SelectionList(id="device-list")
                yield Label("[b]📦 LOCAL APKS[/b]")
                yield SelectionList(id="apk-list")
                yield Button("RUN INSTALL", id="install-btn", variant="success")
                yield Button("LIST APPS (L)", id="list-btn", variant="warning")
                yield Button("REFRESH (R)", id="refresh-btn")
            
            with Vertical(id="main-zone"):
                yield Label("[b]🚀 DEPLOYMENTS[/b]", id="view-title")
                yield ScrollableContainer(id="tasks-container")
                yield DataTable(id="history-table")
                yield Label("[b]📜 SYSTEM LOGS[/b]")
                yield RichLog(id="debug-log", highlight=True, markup=True)
        yield Footer()

    async def on_mount(self) -> None:
        self.registry = load_json(REGISTRY_PATH, {})
        self.history = load_json(HISTORY_PATH, [])
        table = self.query_one(DataTable)
        table.add_columns("Date", "Device", "Activity", "Status")
        for e in self.history:
            table.add_row(e['date'], e['id'], e['activity'], e['status'])
        self.call_after_refresh(self.action_refresh)

    def get_nickname(self, serial: str) -> str:
        if serial not in self.registry:
            self.registry[serial] = f"DEV-{len(self.registry) + 1:02d}"
            save_json(REGISTRY_PATH, self.registry)
        return self.registry[serial]

    def log_message(self, message: str):
        try: self.query_one("#debug-log", RichLog).write(message)
        except: pass

    def action_refresh(self) -> None:
        devices = []
        try:
            output = subprocess.check_output(["adb", "devices"]).decode().splitlines()[1:]
            for l in output:
                if "\t" in l:
                    serial = l.split("\t")[0]
                    devices.append({"id": serial, "name": self.get_nickname(serial)})
        except: self.log_message("[red]ADB Scan Error[/]")

        files = [f for f in os.listdir(APK_DIR) if f.lower().endswith((".apk", ".xapk"))] if os.path.exists(APK_DIR) else []
        self.query_one("#device-list").clear_options()
        self.query_one("#device-list").add_options([(f"{d['name']} ({d['id'][:10]})", d['id']) for d in devices])
        self.query_one("#apk-list").clear_options()
        self.query_one("#apk-list").add_options([(f, f) for f in files])

    # --- BROWSE & UNINSTALL ---
    async def action_list_packages(self) -> None:
        selected = self.query_one("#device-list").selected
        if len(selected) != 1:
            self.notify("Select exactly ONE device to browse apps.", severity="warning")
            return
        serial = selected[0]
        nickname = self.get_nickname(serial)
        self.log_message(f"[yellow]Listing apps on {nickname}...[/]")
        try:
            proc = await asyncio.create_subprocess_exec("adb", "-s", serial, "shell", "pm", "list", "packages", "-3", stdout=asyncio.subprocess.PIPE)
            stdout, _ = await proc.communicate()
            pkgs = [l.replace("package:", "").strip() for l in stdout.decode().splitlines() if l.strip()]
            self.push_screen(PackageBrowserModal(pkgs, nickname), self.handle_batch_uninstall)
        except Exception as e: self.log_message(f"[red]Error: {e}[/]")

    async def handle_batch_uninstall(self, packages: Optional[List[str]]) -> None:
        if not packages: return
        serial = self.query_one("#device-list").selected[0]
        nickname = self.get_nickname(serial)
        for pkg in packages:
            task = InstallTask(serial, nickname, f"RM: {pkg}")
            await self.query_one("#tasks-container").mount(task)
            self.run_worker(self.uninstall_worker(serial, nickname, pkg, task))

    async def uninstall_worker(self, serial: str, nickname: str, pkg: str, widget: InstallTask):
        dt = datetime.now().strftime("%m-%d %H:%M")
        try:
            proc = await asyncio.create_subprocess_exec("adb", "-s", serial, "uninstall", pkg, stdout=asyncio.subprocess.PIPE)
            stdout, _ = await proc.communicate()
            status = "Success" if b"Success" in stdout else "Failed"
            widget.update_status(status, 100)
            self.record_history(dt, nickname, f"RM: {pkg}", status)
        except: widget.update_status("Error", 0)

    # --- INSTALLATION ---
    async def action_install(self):
        devs, files = self.query_one("#device-list").selected, self.query_one("#apk-list").selected
        for s in devs:
            n = self.get_nickname(s)
            for f in files:
                task = InstallTask(s, n, f)
                await self.query_one("#tasks-container").mount(task)
                self.run_worker(self.install_worker(s, n, f, task))

    async def install_worker(self, serial: str, nickname: str, file_name: str, widget: InstallTask):
        dt = datetime.now().strftime("%m-%d %H:%M")
        file_path = os.path.join(APK_DIR, file_name)
        is_xapk = file_name.lower().endswith((".xapk", ".xpk"))
        try:
            if is_xapk:
                temp_dir = tempfile.mkdtemp()
                with zipfile.ZipFile(file_path, 'r') as z: z.extractall(temp_dir)
                apks = [os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.endswith(".apk")]
                cmd = ["adb", "-s", serial, "install-multiple", "-r"] + apks
            else:
                cmd = ["adb", "-s", serial, "install", "-r", file_path]
            
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE)
            await proc.communicate()
            res = "Success" if proc.returncode == 0 else "Failed"
            widget.update_status(res, 100)
            self.record_history(dt, nickname, f"IN: {file_name}", res)
            if is_xapk: shutil.rmtree(temp_dir)
        except: widget.update_status("Error", 0)

    def record_history(self, dt, name, activity, status):
        log = {"date": dt, "id": name, "activity": activity, "status": status}
        self.history.append(log)
        save_json(HISTORY_PATH, self.history)
        self.query_one(DataTable).add_row(dt, name, activity, status)

    def action_toggle_history(self) -> None:
        l, h = self.query_one("#tasks-container"), self.query_one("#history-table")
        l.styles.display, h.styles.display = ("none", "block") if l.styles.display != "none" else ("block", "none")

    # --- WIRELESS ---
    def action_wireless_pair(self) -> None: self.push_screen(PairModal(), self.handle_pairing)
    async def handle_pairing(self, d):
        if d:
            p = await asyncio.create_subprocess_exec("adb", "pair", d['address'], d['code'], stdout=asyncio.subprocess.PIPE)
            s, _ = await p.communicate()
            self.log_message(s.decode().strip())

    def action_wireless_connect(self) -> None: self.push_screen(ConnectModal(), self.handle_connection)
    async def handle_connection(self, ip):
        if ip:
            p = await asyncio.create_subprocess_exec("adb", "connect", ip, stdout=asyncio.subprocess.PIPE)
            s, _ = await p.communicate()
            self.log_message(s.decode().strip())
            self.action_refresh()

    async def action_kill_adb(self) -> None:
        self.log_message("[yellow]Resetting ADB...[/]")
        subprocess.run(["adb", "kill-server"])
        subprocess.run(["adb", "start-server"])
        self.action_refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "refresh-btn": self.action_refresh()
        elif event.button.id == "install-btn": self.run_worker(self.action_install())
        elif event.button.id == "list-btn": self.run_worker(self.action_list_packages())

if __name__ == "__main__":
    AdvancedAdbManager().run()