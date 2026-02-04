import os
import sys
import json
import subprocess
import time
import psutil
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.table import Table
from rich.prompt import Confirm

# --- Helper Functions (Shared) ---

def shutdown_chrome(log_func):
    terminated_chromes = set()
    for process in psutil.process_iter():
        try:
            if sys.platform == 'darwin':
                if not process.name().startswith('Google Chrome'):
                    continue
            elif os.path.splitext(process.name())[0] != 'chrome':
                continue
            elif not process.is_running():
                continue
            elif process.parent() is not None and process.parent().name() == process.name():
                continue
            location = process.exe()
            process.kill()
            terminated_chromes.add(location)
        except psutil.NoSuchProcess:
            pass
    return terminated_chromes

def get_last_version(user_data_path):
    last_version_file = os.path.join(user_data_path, 'Last Version')
    if not os.path.exists(last_version_file):
        return None
    with open(last_version_file, 'r', encoding='utf-8') as fp:
        return fp.read()

def set_all_is_glic_eligible(obj):
    modified = False
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == 'is_glic_eligible' and value != True:
                obj[key] = True
                modified = True
            elif isinstance(value, (dict, list)):
                if set_all_is_glic_eligible(value):
                    modified = True
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                if set_all_is_glic_eligible(item):
                    modified = True
    return modified

def patch_local_state(user_data_path, last_version, log_func):
    local_state_file = os.path.join(user_data_path, 'Local State')
    if not os.path.exists(local_state_file):
        log_func(f"[yellow]⚠️ Local State file not found[/yellow]")
        return

    with open(local_state_file, 'r', encoding='utf-8') as fp:
        local_state = json.load(fp)

    modified = False

    if set_all_is_glic_eligible(local_state):
        modified = True
        log_func("  [green]✓[/green] Patched is_glic_eligible")

    if local_state.get('variations_country') != 'us':
        local_state['variations_country'] = 'us'
        modified = True
        log_func("  [green]✓[/green] Patched variations_country")

    if 'variations_permanent_consistency_country' in local_state:
        if isinstance(local_state['variations_permanent_consistency_country'], list) and \
           len(local_state['variations_permanent_consistency_country']) >= 2:
            if local_state['variations_permanent_consistency_country'][0] != last_version or \
               local_state['variations_permanent_consistency_country'][1] != 'us':
                local_state['variations_permanent_consistency_country'][0] = last_version
                local_state['variations_permanent_consistency_country'][1] = 'us'
                modified = True
                log_func("  [green]✓[/green] Patched variations_permanent_consistency_country")

    if modified:
        with open(local_state_file, 'w', encoding='utf-8') as fp:
            json.dump(local_state, fp)
        log_func("  [bold green]✅ Local State patched successfully[/bold green]")
    else:
        log_func("  [blue]ℹ️ No patching needed[/blue]")


# --- TUI App ---

class TUIApp:
    def __init__(self):
        self.console = Console()
        self.log_content = Text()
        self.layout = Layout()
        self.init_layout()
        self.version_and_user_data_path = {}

    def init_layout(self):
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )
        self.layout["header"].update(Panel(Text("Enable Chrome AI ✨", justify="center", style="bold blue"), style="blue"))
        self.layout["footer"].update(Panel(Text("Press Ctrl+C to exit", justify="center", style="dim")))

    def detect_chrome(self):
        os_and_user_data_paths = {
            'win32': {
                'Stable': '~/AppData/Local/Google/Chrome/User Data',
                'Canary': '~/AppData/Local/Google/Chrome SxS/User Data',
                'Dev': '~/AppData/Local/Google/Chrome Dev/User Data',
                'Beta': '~/AppData/Local/Google/Chrome Beta/User Data',
            },
            'linux': {
                'Stable': '~/.config/google-chrome',
                'Canary': '~/.config/google-chrome-canary',
                'Dev': '~/.config/google-chrome-unstable',
                'Beta': '~/.config/google-chrome-beta',
            },
            'darwin': {
                'Stable': '~/Library/Application Support/Google/Chrome',
                'Canary': '~/Library/Application Support/Google/Chrome Canary',
                'Dev': '~/Library/Application Support/Google/Chrome Dev',
                'Beta': '~/Library/Application Support/Google/Chrome Beta',
            },
        }

        found = False
        table = Table(title="Detected Chrome Versions", box=None)
        table.add_column("Version", style="cyan")
        table.add_column("Path", style="dim")

        for platform, paths in os_and_user_data_paths.items():
            if sys.platform.startswith(platform):
                for version, path in paths.items():
                    path = os.path.abspath(os.path.expanduser(path))
                    if os.path.exists(path):
                        self.version_and_user_data_path[version] = path
                        table.add_row(f"Chrome {version}", path)
                        found = True
                break

        if found:
            self.console.print(table)
        else:
            self.console.print("[bold red]❌ No installed Chrome detected[/bold red]")
            sys.exit(1)

    def log(self, message):
        self.log_content.append(message + "\n")
        # Keep only last 20 lines
        lines = self.log_content.plain.splitlines()
        if len(lines) > 20:
             self.log_content = Text("\n".join(lines[-20:]) + "\n")

    def run(self):
        self.console.clear()
        self.console.print(Panel(Text("Enable Chrome AI ✨\nEnable Gemini, History Search, DevTools AI", justify="center", style="bold blue")))

        self.detect_chrome()
        self.console.print()

        if not Confirm.ask("Do you want to proceed with patching?", default=True):
            self.console.print("[yellow]Operation cancelled.[/yellow]")
            return

        self.console.clear()

        # Setup Live Display
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        )
        task_id = progress.add_task("Initializing...", total=100)

        self.layout["body"].split(
            Layout(Panel(progress, title="Progress", border_style="green"), size=5),
            Layout(Panel(self.log_content, title="Logs", border_style="blue"), name="logs")
        )

        with Live(self.layout, refresh_per_second=4, screen=True) as live:
            def live_log(msg):
                self.log(msg)
                self.layout["logs"].update(Panel(self.log_content, title="Logs", border_style="blue"))

            # Step 1: Shutdown
            progress.update(task_id, description="Closing Chrome...", advance=10)
            terminated_chromes = shutdown_chrome(live_log)
            if terminated_chromes:
                live_log("[green]✅ Chrome browser closed[/green]")
            else:
                live_log("[dim]ℹ️ Chrome was not running[/dim]")

            # Step 2: Patch
            total = len(self.version_and_user_data_path)
            for i, (version, user_data_path) in enumerate(self.version_and_user_data_path.items()):
                progress.update(task_id, description=f"Patching Chrome {version}...")

                last_version = get_last_version(user_data_path)
                if last_version is None:
                    live_log(f"[yellow]⚠️ Chrome {version}: Unable to get version info[/yellow]")
                    continue

                live_log(f"🔧 Patching Chrome {version} ([cyan]{last_version}[/cyan])")
                patch_local_state(user_data_path, last_version, live_log)

                step_progress = int(60 / total)
                progress.advance(task_id, step_progress)
                time.sleep(0.5) # Aesthetic delay

            # Step 3: Restart
            progress.update(task_id, description="Restarting Chrome...", advance=20)
            if terminated_chromes:
                live_log("🚀 Restarting Chrome...")
                for chrome in terminated_chromes:
                    subprocess.Popen([chrome], stderr=subprocess.DEVNULL)
                live_log("[green]✅ Chrome restarted[/green]")

            progress.update(task_id, completed=100, description="[bold green]Done![/bold green]")
            live_log("[bold green]🎉 All operations completed![/bold green]")
            time.sleep(2) # Let user see the success message

        self.console.print("[bold green]Success! Chrome AI features enabled.[/bold green]")

if __name__ == '__main__':
    try:
        app = TUIApp()
        app.run()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
