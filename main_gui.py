import os
import sys
import json
import subprocess
import psutil
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QGroupBox, QListWidget, QListWidgetItem,
    QMessageBox, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont


class PatchWorker(QThread):
    """Worker thread for running patch operations without blocking GUI."""
    log_signal = Signal(str)
    finished_signal = Signal(bool, str)
    progress_signal = Signal(int)

    def __init__(self, version_and_user_data_path):
        super().__init__()
        self.version_and_user_data_path = version_and_user_data_path
        self.terminated_chromes = set()

    def log(self, message):
        self.log_signal.emit(message)

    def run(self):
        try:
            # Step 1: Shutdown Chrome
            self.progress_signal.emit(10)
            self.terminated_chromes = self.shutdown_chrome()
            if len(self.terminated_chromes) > 0:
                self.log("✅ 已关闭 Chrome 浏览器")

            # Step 2: Patch each version
            total = len(self.version_and_user_data_path)
            for i, (version, user_data_path) in enumerate(self.version_and_user_data_path.items()):
                progress = 20 + int(60 * (i + 1) / total)
                self.progress_signal.emit(progress)
                
                last_version = self.get_last_version(user_data_path)
                if last_version is None:
                    self.log(f"⚠️ Chrome {version}: 无法获取版本信息")
                    continue
                
                self.log(f"🔧 正在修补 Chrome {version} ({last_version})")
                self.patch_local_state(user_data_path, last_version)

            # Step 3: Restart Chrome
            self.progress_signal.emit(90)
            if len(self.terminated_chromes) > 0:
                self.log("🚀 正在重启 Chrome...")
                for chrome in self.terminated_chromes:
                    subprocess.Popen([chrome], stderr=subprocess.DEVNULL)
                self.log("✅ Chrome 已重启")

            self.progress_signal.emit(100)
            self.finished_signal.emit(True, "🎉 所有操作已完成！Chrome AI 功能已启用。")
        except Exception as e:
            self.finished_signal.emit(False, f"❌ 发生错误: {str(e)}")

    def shutdown_chrome(self):
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

    def get_last_version(self, user_data_path):
        last_version_file = os.path.join(user_data_path, 'Last Version')
        if not os.path.exists(last_version_file):
            return None
        with open(last_version_file, 'r', encoding='utf-8') as fp:
            return fp.read()

    def set_all_is_glic_eligible(self, obj):
        """Recursively find and set all is_glic_eligible to true."""
        modified = False
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == 'is_glic_eligible' and value != True:
                    obj[key] = True
                    modified = True
                elif isinstance(value, (dict, list)):
                    if self.set_all_is_glic_eligible(value):
                        modified = True
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    if self.set_all_is_glic_eligible(item):
                        modified = True
        return modified

    def patch_local_state(self, user_data_path, last_version):
        local_state_file = os.path.join(user_data_path, 'Local State')
        if not os.path.exists(local_state_file):
            self.log(f"  ⚠️ Local State 文件不存在")
            return

        with open(local_state_file, 'r', encoding='utf-8') as fp:
            local_state = json.load(fp)

        modified = False

        # 1. Set all is_glic_eligible to true (recursive)
        if self.set_all_is_glic_eligible(local_state):
            modified = True
            self.log("  ✓ 已修补 is_glic_eligible")

        # 2. Set variations_country to "us" (root level)
        if local_state.get('variations_country') != 'us':
            local_state['variations_country'] = 'us'
            modified = True
            self.log("  ✓ 已修补 variations_country")

        # 3. Set variations_permanent_consistency_country
        if 'variations_permanent_consistency_country' in local_state:
            if isinstance(local_state['variations_permanent_consistency_country'], list) and \
               len(local_state['variations_permanent_consistency_country']) >= 2:
                if local_state['variations_permanent_consistency_country'][0] != last_version or \
                   local_state['variations_permanent_consistency_country'][1] != 'us':
                    local_state['variations_permanent_consistency_country'][0] = last_version
                    local_state['variations_permanent_consistency_country'][1] = 'us'
                    modified = True
                    self.log("  ✓ 已修补 variations_permanent_consistency_country")

        if modified:
            with open(local_state_file, 'w', encoding='utf-8') as fp:
                json.dump(local_state, fp)
            self.log("  ✅ Local State 修补成功")
        else:
            self.log("  ℹ️ 无需修补（已是最新状态）")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.version_and_user_data_path = {}
        self.worker = None
        self.init_ui()
        self.detect_chrome()

    def init_ui(self):
        self.setWindowTitle("Enable Chrome AI ✨")
        self.setMinimumSize(600, 500)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e2e;
            }
            QLabel {
                color: #cdd6f4;
            }
            QGroupBox {
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QListWidget {
                background-color: #313244;
                color: #cdd6f4;
                border: none;
                border-radius: 6px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #45475a;
            }
            QTextEdit {
                background-color: #313244;
                color: #a6e3a1;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-family: Consolas, monospace;
            }
            QPushButton {
                background-color: #89b4fa;
                color: #1e1e2e;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #b4befe;
            }
            QPushButton:disabled {
                background-color: #45475a;
                color: #6c7086;
            }
            QProgressBar {
                background-color: #313244;
                border: none;
                border-radius: 4px;
                height: 8px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #a6e3a1;
                border-radius: 4px;
            }
        """)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title
        title_label = QLabel("Enable Chrome AI ✨")
        title_label.setFont(QFont("Segoe UI", 24, QFont.Bold))
        title_label.setStyleSheet("color: #89b4fa;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Description
        desc_label = QLabel("一键启用 Chrome 内置 AI 功能：Gemini、AI 历史搜索、DevTools AI 等")
        desc_label.setFont(QFont("Segoe UI", 11))
        desc_label.setStyleSheet("color: #bac2de;")
        desc_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc_label)

        # Chrome versions group
        chrome_group = QGroupBox("检测到的 Chrome 版本")
        chrome_layout = QVBoxLayout(chrome_group)
        self.chrome_list = QListWidget()
        self.chrome_list.setMinimumHeight(100)
        chrome_layout.addWidget(self.chrome_list)
        layout.addWidget(chrome_group)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Action button
        self.patch_btn = QPushButton("🚀 一键启用 Chrome AI")
        self.patch_btn.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.patch_btn.setCursor(Qt.PointingHandCursor)
        self.patch_btn.clicked.connect(self.start_patch)
        layout.addWidget(self.patch_btn)

        # Log output group
        log_group = QGroupBox("操作日志")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(150)
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_group)

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

        self.chrome_list.clear()
        self.version_and_user_data_path = {}

        for platform, version_and_user_data_path in os_and_user_data_paths.items():
            if sys.platform.startswith(platform):
                for version, user_data_path in version_and_user_data_path.items():
                    user_data_path = os.path.abspath(os.path.expanduser(user_data_path))
                    if os.path.exists(user_data_path):
                        self.version_and_user_data_path[version] = user_data_path
                        item = QListWidgetItem(f"🌐 Chrome {version}")
                        item.setToolTip(user_data_path)
                        self.chrome_list.addItem(item)
                break

        if len(self.version_and_user_data_path) == 0:
            self.chrome_list.addItem("❌ 未检测到已安装的 Chrome")
            self.patch_btn.setEnabled(False)
            self.log("⚠️ 未检测到已安装的 Chrome 浏览器")
        else:
            self.log(f"✅ 检测到 {len(self.version_and_user_data_path)} 个 Chrome 版本")

    def log(self, message):
        """Append message to log."""
        self.log_text.append(message)

    def start_patch(self):
        """Start the patch process."""
        self.patch_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.log_text.clear()
        self.log("🔄 开始执行修补操作...")

        self.worker = PatchWorker(self.version_and_user_data_path)
        self.worker.log_signal.connect(self.log)
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.finished_signal.connect(self.on_patch_finished)
        self.worker.start()

    def on_patch_finished(self, success, message):
        """Handle patch completion."""
        self.patch_btn.setEnabled(True)
        self.log(message)
        
        # Create message box with light theme for better readability
        msg_box = QMessageBox(self)
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #ffffff;
            }
            QMessageBox QLabel {
                color: #1e1e2e;
                font-size: 14px;
            }
            QMessageBox QPushButton {
                background-color: #89b4fa;
                color: #1e1e2e;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover {
                background-color: #b4befe;
            }
        """)
        
        if success:
            msg_box.setWindowTitle("完成")
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setText(message)
        else:
            msg_box.setWindowTitle("错误")
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setText(message)
        
        msg_box.exec()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
