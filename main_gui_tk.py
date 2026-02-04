import os
import sys
import json
import subprocess
import threading
import queue
import psutil
import tkinter as tk
from tkinter import ttk, messagebox

# --- Helper Functions ---

def shutdown_chrome():
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
    """Recursively find and set all is_glic_eligible to true."""
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
        log_func(f"  ⚠️ Local State 文件不存在")
        return

    with open(local_state_file, 'r', encoding='utf-8') as fp:
        local_state = json.load(fp)

    modified = False

    # 1. Set all is_glic_eligible to true (recursive)
    if set_all_is_glic_eligible(local_state):
        modified = True
        log_func("  ✓ 已修补 is_glic_eligible")

    # 2. Set variations_country to "us" (root level)
    if local_state.get('variations_country') != 'us':
        local_state['variations_country'] = 'us'
        modified = True
        log_func("  ✓ 已修补 variations_country")

    # 3. Set variations_permanent_consistency_country
    if 'variations_permanent_consistency_country' in local_state:
        if isinstance(local_state['variations_permanent_consistency_country'], list) and \
           len(local_state['variations_permanent_consistency_country']) >= 2:
            if local_state['variations_permanent_consistency_country'][0] != last_version or \
               local_state['variations_permanent_consistency_country'][1] != 'us':
                local_state['variations_permanent_consistency_country'][0] = last_version
                local_state['variations_permanent_consistency_country'][1] = 'us'
                modified = True
                log_func("  ✓ 已修补 variations_permanent_consistency_country")

    if modified:
        with open(local_state_file, 'w', encoding='utf-8') as fp:
            json.dump(local_state, fp)
        log_func("  ✅ Local State 修补成功")
    else:
        log_func("  ℹ️ 无需修补（已是最新状态）")

# --- Worker Logic ---

def run_patch_process(msg_queue, version_and_user_data_path):
    def log(message):
        msg_queue.put(('log', message))

    try:
        # Step 1: Shutdown Chrome
        msg_queue.put(('progress', 10))
        terminated_chromes = shutdown_chrome()
        if len(terminated_chromes) > 0:
            log("✅ 已关闭 Chrome 浏览器")

        # Step 2: Patch each version
        total = len(version_and_user_data_path)
        for i, (version, user_data_path) in enumerate(version_and_user_data_path.items()):
            progress = 20 + int(60 * (i + 1) / total)
            msg_queue.put(('progress', progress))

            last_version = get_last_version(user_data_path)
            if last_version is None:
                log(f"⚠️ Chrome {version}: 无法获取版本信息")
                continue

            log(f"🔧 正在修补 Chrome {version} ({last_version})")
            patch_local_state(user_data_path, last_version, log)

        # Step 3: Restart Chrome
        msg_queue.put(('progress', 90))
        if len(terminated_chromes) > 0:
            log("🚀 正在重启 Chrome...")
            for chrome in terminated_chromes:
                subprocess.Popen([chrome], stderr=subprocess.DEVNULL)
            log("✅ Chrome 已重启")

        msg_queue.put(('progress', 100))
        msg_queue.put(('finished', (True, "🎉 所有操作已完成！Chrome AI 功能已启用。")))
    except Exception as e:
        msg_queue.put(('finished', (False, f"❌ 发生错误: {str(e)}")))

# --- GUI ---

class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.version_and_user_data_path = {}
        self.msg_queue = queue.Queue()
        self.init_ui()
        self.detect_chrome()

    def init_ui(self):
        self.title("Enable Chrome AI ✨")
        self.geometry("600x500")
        self.configure(bg="#1e1e2e")
        self.minsize(600, 500)

        # Style configuration
        style = ttk.Style()
        style.theme_use('default')
        style.configure("TProgressbar", thickness=10, troughcolor="#313244", background="#a6e3a1", borderwidth=0)

        # Central frame (shim to add padding)
        main_frame = tk.Frame(self, bg="#1e1e2e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title
        title_label = tk.Label(main_frame, text="Enable Chrome AI ✨",
                               font=("Segoe UI", 24, "bold"),
                               bg="#1e1e2e", fg="#89b4fa")
        title_label.pack(pady=(0, 5))

        # Description
        desc_label = tk.Label(main_frame, text="一键启用 Chrome 内置 AI 功能：Gemini、AI 历史搜索、DevTools AI 等",
                              font=("Segoe UI", 11),
                              bg="#1e1e2e", fg="#bac2de")
        desc_label.pack(pady=(0, 15))

        # Chrome versions group
        chrome_group = tk.LabelFrame(main_frame, text="检测到的 Chrome 版本",
                                     bg="#1e1e2e", fg="#cdd6f4",
                                     font=("Segoe UI", 9, "bold"),
                                     bd=1, relief="solid")
        chrome_group.pack(fill=tk.X, pady=(0, 10))

        # Listbox for Chrome versions
        self.chrome_list = tk.Listbox(chrome_group,
                                      bg="#313244", fg="#cdd6f4",
                                      selectbackground="#45475a", selectforeground="#cdd6f4",
                                      bd=0, highlightthickness=0, height=4,
                                      font=("Segoe UI", 10))
        self.chrome_list.pack(fill=tk.X, padx=5, pady=5)

        # Progress bar
        self.progress_bar = ttk.Progressbar(main_frame, style="TProgressbar", orient="horizontal", mode="determinate", length=100)
        # Hidden initially by not packing, or packing with 0 height?
        # Tkinter widgets are hard to "hide" without removing from layout.
        # We will pack it but maybe keep it hidden or just show empty.
        # Let's pack it but manage visibility or just let it be empty.
        # The original had setVisible(False). We can use pack_forget().

        # Action button
        # Using tk.Button for better color control on standard themes
        self.patch_btn = tk.Button(main_frame, text="🚀 一键启用 Chrome AI",
                                   command=self.start_patch,
                                   bg="#89b4fa", fg="#1e1e2e",
                                   activebackground="#b4befe", activeforeground="#1e1e2e",
                                   font=("Segoe UI", 12, "bold"),
                                   bd=0, padx=24, pady=8, cursor="hand2")
        self.patch_btn.pack(pady=10)

        # Log output group
        log_group = tk.LabelFrame(main_frame, text="操作日志",
                                  bg="#1e1e2e", fg="#cdd6f4",
                                  font=("Segoe UI", 9, "bold"),
                                  bd=1, relief="solid")
        log_group.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_group,
                                bg="#313244", fg="#a6e3a1",
                                bd=0, highlightthickness=0,
                                font=("Consolas", 10), state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def detect_chrome(self):
        """Detect installed Chrome versions."""
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

        self.chrome_list.delete(0, tk.END)
        self.version_and_user_data_path = {}

        found = False
        for platform, version_and_user_data_path in os_and_user_data_paths.items():
            if sys.platform.startswith(platform):
                for version, user_data_path in version_and_user_data_path.items():
                    user_data_path = os.path.abspath(os.path.expanduser(user_data_path))
                    if os.path.exists(user_data_path):
                        self.version_and_user_data_path[version] = user_data_path
                        self.chrome_list.insert(tk.END, f"🌐 Chrome {version}")
                        found = True
                break

        if not found:
            self.chrome_list.insert(tk.END, "❌ 未检测到已安装的 Chrome")
            self.patch_btn.config(state=tk.DISABLED, bg="#45475a", fg="#6c7086")
            self.log("⚠️ 未检测到已安装的 Chrome 浏览器")
        else:
            self.log(f"✅ 检测到 {len(self.version_and_user_data_path)} 个 Chrome 版本")

    def log(self, message):
        """Append message to log."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def start_patch(self):
        """Start the patch process."""
        self.patch_btn.config(state=tk.DISABLED, bg="#45475a", fg="#6c7086", cursor="arrow")

        # Show progress bar
        self.progress_bar.pack(before=self.patch_btn, fill=tk.X, pady=(0, 10))
        self.progress_bar['value'] = 0

        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.log("🔄 开始执行修补操作...")

        thread = threading.Thread(target=run_patch_process, args=(self.msg_queue, self.version_and_user_data_path))
        thread.start()

        self.after(100, self.check_queue)

    def check_queue(self):
        try:
            while True:
                msg_type, data = self.msg_queue.get_nowait()
                if msg_type == 'log':
                    self.log(data)
                elif msg_type == 'progress':
                    self.progress_bar['value'] = data
                elif msg_type == 'finished':
                    success, message = data
                    self.on_patch_finished(success, message)
                    return # Stop polling
        except queue.Empty:
            pass

        self.after(100, self.check_queue)

    def on_patch_finished(self, success, message):
        self.patch_btn.config(state=tk.NORMAL, bg="#89b4fa", fg="#1e1e2e", cursor="hand2")
        self.progress_bar.pack_forget() # Hide progress bar
        self.log(message)

        if success:
            messagebox.showinfo("完成", message)
        else:
            messagebox.showwarning("错误", message)

def main():
    app = MainWindow()
    app.mainloop()

if __name__ == '__main__':
    main()
