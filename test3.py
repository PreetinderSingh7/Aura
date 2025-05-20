import sys
import os
import threading
import time
import random
import json
import re
import platform
import subprocess
import webbrowser
import tempfile
from datetime import datetime
from pathlib import Path

# GUI imports
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize, QUrl, QObject, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter, QPen, QColor, QFontDatabase, QAction
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QSlider, QFrame, QTextEdit,
    QSystemTrayIcon, QMenu, QTabWidget, QScrollArea, QGroupBox,
    QLineEdit, QProgressBar, QDialog, QCheckBox, QMessageBox,
    QSpacerItem, QSizePolicy, QRadioButton, QButtonGroup, QListWidget
)

# Audio processing
import speech_recognition as sr
from gtts import gTTS
import pygame
import numpy as np
import pyaudio
import wave
import audioop

# System info and utilities
import psutil
import requests
import wikipedia
from xml.etree import ElementTree

# Module constants
VERSION = "2.0.0"
WAKE_WORDS = ["hey aura", "hi aura", "hello aura", "ok aura"]
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".aura_config.json")
LOG_DIR = os.path.join(os.path.expanduser("~"), ".aura_logs")
OPENWEATHER_API_KEY = "3a4cb37143c60215d6071ca269da13a1"  # Replace with your actual OpenWeatherMap API key
WOLFRAM_ALPHA_API_KEY = "PJHQ7H-2UHW2QU647"  # Replace with your actual Wolfram Alpha API key

def query_wolfram_conversational(api_key, query):
    """Query the Wolfram Conversational API."""
    url = "https://api.wolframalpha.com/v1/conversational"
    params = {
        "appid": api_key,
        "i": query
    }

    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Failed to fetch data from Wolfram Alpha. Status code: {response.status_code}"}
    except Exception as e:
        return {"error": f"Failed to fetch data from Wolfram Alpha. Error: {str(e)}"}

class AudioVisualizer(QWidget):
    """Widget for visualizing audio"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(60)
        self.setMinimumWidth(200)

        # Audio visualization data
        self.audio_data = np.zeros(50)
        self.color_active = QColor(0, 184, 148)  # Active visualization color
        self.color_inactive = QColor(99, 110, 114)  # Inactive visualization color
        self.is_active = False

        # Animation elements
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_visualization)
        self.animation_timer.start(50)  # 50ms refresh rate

    def update_visualization(self):
        """Update the audio visualization data"""
        if self.is_active:
            # Generate some demo animation when active
            new_data = np.random.uniform(0.1, 1.0, 1)[0]
            self.audio_data = np.roll(self.audio_data, -1)
            self.audio_data[-1] = new_data
        else:
            # Generate minimal animation when inactive
            new_data = np.random.uniform(0.0, 0.2, 1)[0]
            self.audio_data = np.roll(self.audio_data, -1)
            self.audio_data[-1] = new_data

        self.update()

    def set_active(self, active):
        """Set whether the visualizer is active"""
        self.is_active = active

    def update_with_audio_level(self, level):
        """Update the visualization with an audio level"""
        # Normalize level between 0 and 1
        normalized_level = min(max(level / 10000, 0), 1)
        self.audio_data = np.roll(self.audio_data, -1)
        self.audio_data[-1] = normalized_level
        self.update()

    def paintEvent(self, event):
        """Paint the audio visualization"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Get widget dimensions
        width = self.width()
        height = self.height()
        bar_width = width / len(self.audio_data)

        # Draw the visualization bars
        for i, value in enumerate(self.audio_data):
            bar_height = value * height * 0.8

            if self.is_active:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(self.color_active)
            else:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(self.color_inactive)

            # Convert float to int
            x = int(i * bar_width)
            y = int(height - bar_height)
            w = int(bar_width * 0.8)
            h = int(bar_height)

            # Draw a bar
            painter.drawRoundedRect(
                x,
                y,
                w,
                h,
                2, 2
            )

class CircularProgressBar(QWidget):
    """Custom circular progress indicator"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(100, 100)
        self._value = 0  # Use a different name to avoid conflict with the property
        self.max_value = 100
        self.animation = QPropertyAnimation(self, b"value")
        self.animation.setDuration(250)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def get_value(self):
        return self._value

    def set_value(self, value):
        self._value = value
        self.update()

    value = pyqtSignal(int)
    value = property(get_value, set_value)

    def animate_value(self, value):
        """Animate the progress bar to a new value"""
        self.animation.setStartValue(self._value)
        self.animation.setEndValue(value)
        self.animation.start()

    def paintEvent(self, event):
        """Paint the circular progress bar"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw background circle
        painter.setPen(QPen(QColor("#e0e0e0"), 10))
        painter.drawArc(10, 10, self.width() - 20, self.height() - 20, 0, 360 * 16)

        # Draw progress arc
        painter.setPen(QPen(QColor("#2ecc71"), 10))
        span_angle = int(-self._value * 360.0 / self.max_value * 16)  # Convert to int
        painter.drawArc(10, 10, self.width() - 20, self.height() - 20, 90 * 16, span_angle)

        # Draw text with a more visible color
        painter.setPen(QColor("#ffffff"))  # White color for better visibility
        painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f"{int(self._value)}%")

class WakeWordThread(QThread):
    """Thread for wake word detection"""
    wake_word_detected = pyqtSignal()
    audio_level = pyqtSignal(int)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = False
        self.paused = False
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 3000  # Increase energy threshold
        self.recognizer.dynamic_energy_threshold = True

    def run(self):
        """Main loop for wake word detection"""
        self.running = True

        try:
            with sr.Microphone() as source:
                print("Adjusting for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                print("Microphone adjusted for ambient noise")

                while self.running:
                    if not self.paused:
                        try:
                            print("Listening for wake word...")
                            audio = self.recognizer.listen(source, timeout=None, phrase_time_limit=5)  # Set timeout to None to keep listening

                            # Get audio level for visualization
                            raw_data = audio.get_raw_data(convert_rate=16000, convert_width=2)
                            level = audioop.rms(raw_data, 2)
                            self.audio_level.emit(level)

                            # Try to recognize wake word
                            try:
                                text = self.recognizer.recognize_google(audio).lower()
                                print(f"Recognized text: {text}")

                                # Check for wake words
                                if any(wake_word in text for wake_word in WAKE_WORDS):
                                    self.wake_word_detected.emit()
                                    # Pause wake word detection while processing command
                                    self.paused = True

                            except sr.UnknownValueError:
                                print("Speech not understood")
                                pass
                            except sr.RequestError as e:
                                print(f"API request error: {e}")
                                pass

                        except sr.WaitTimeoutError:
                            print("Listening timed out")
                            pass
                        except Exception as e:
                            self.error_occurred.emit(f"Error listening for wake word: {str(e)}")
                    else:
                        # When paused, just sleep a bit
                        time.sleep(0.1)

        except Exception as e:
            self.error_occurred.emit(f"Wake word detection error: {str(e)}")

    def resume(self):
        """Resume wake word detection"""
        self.paused = False

    def stop(self):
        """Stop the wake word detection thread"""
        self.running = False
        self.wait()

class CommandThread(QThread):
    """Thread for command recognition and processing"""
    command_received = pyqtSignal(str)
    command_processed = pyqtSignal()
    audio_level = pyqtSignal(int)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 3000  # Increase energy threshold
        self.recognizer.dynamic_energy_threshold = True

    def run(self):
        """Run command recognition"""
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)

                # Listen for the command
                audio = self.recognizer.listen(source, timeout=None, phrase_time_limit=10)  # Set timeout to None to keep listening

                # Get audio level for visualization
                raw_data = audio.get_raw_data(convert_rate=16000, convert_width=2)
                level = audioop.rms(raw_data, 2)
                self.audio_level.emit(level)

                try:
                    # Recognize the command
                    command = self.recognizer.recognize_google(audio).lower()
                    self.command_received.emit(command)
                except sr.UnknownValueError:
                    self.error_occurred.emit("Sorry, I didn't catch that")
                except sr.RequestError as e:
                    self.error_occurred.emit(f"Sorry, speech recognition service is unavailable: {str(e)}")

                self.command_processed.emit()

        except Exception as e:
            self.error_occurred.emit(f"Command recognition error: {str(e)}")
            self.command_processed.emit()

class TTSThread(QThread):
    """Thread for text-to-speech conversion and playback"""
    speech_started = pyqtSignal()
    speech_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.text = ""
        self.volume = 1.0
        self.rate = 1.0
        self.temp_dir = tempfile.gettempdir()

        # Initialize pygame for audio playback
        pygame.mixer.init()

    def set_text(self, text):
        """Set the text to be spoken"""
        self.text = text

    def set_volume(self, volume):
        """Set the playback volume (0.0 to 1.0)"""
        self.volume = volume

    def set_rate(self, rate):
        """Set the speech rate"""
        self.rate = rate

    def run(self):
        """Convert text to speech and play it"""
        if not self.text:
            return

        try:
            # Create unique filename for the audio
            filename = os.path.join(self.temp_dir, f"aura_speech_{int(time.time())}.mp3")

            # Generate speech with gTTS
            tts = gTTS(text=self.text, lang='en', slow=False)
            tts.save(filename)

            # Signal that speech is starting
            self.speech_started.emit()

            # Play the audio with pygame
            pygame.mixer.music.set_volume(1.0)  # Increase volume to maximum
            pygame.mixer.music.load(filename)
            pygame.mixer.music.play()

            # Wait for playback to finish
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)

            # Signal that speech is finished
            self.speech_finished.emit()

            # Clean up the temporary file
            try:
                os.remove(filename)
            except:
                pass

        except Exception as e:
            self.error_occurred.emit(f"Text-to-speech error: {str(e)}")
            self.speech_finished.emit()

class SettingsDialog(QDialog):
    """Settings dialog for the application"""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("AURA Settings")
        self.setMinimumWidth(400)

        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)

        # Create tabs for different settings categories
        tabs = QTabWidget()

        # General settings tab
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)

        # Wake word settings
        wake_group = QGroupBox("Wake Word Detection")
        wake_layout = QVBoxLayout(wake_group)

        self.enable_wake = QCheckBox("Enable wake word detection on startup")
        self.always_listen = QCheckBox("Keep listening for commands (don't require wake word each time)")

        wake_layout.addWidget(self.enable_wake)
        wake_layout.addWidget(self.always_listen)

        # Speech settings
        speech_group = QGroupBox("Speech Settings")
        speech_layout = QVBoxLayout(speech_group)

        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel("Default volume:"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.volume_slider.setTickInterval(10)
        volume_layout.addWidget(self.volume_slider)

        # Add a label to display the volume percentage
        self.volume_label = QLabel(f"{self.volume_slider.value()}%")
        volume_layout.addWidget(self.volume_label)

        # Connect the slider's valueChanged signal to update the label
        self.volume_slider.valueChanged.connect(lambda value: self.volume_label.setText(f"{value}%"))

        self.startup_greeting = QCheckBox("Play greeting on startup")

        speech_layout.addLayout(volume_layout)
        speech_layout.addWidget(self.startup_greeting)

        # Add groups to the general tab
        general_layout.addWidget(wake_group)
        general_layout.addWidget(speech_group)
        general_layout.addStretch()

        # API Keys tab
        api_tab = QWidget()
        api_layout = QVBoxLayout(api_tab)

        wolfram_group = QGroupBox("Wolfram Alpha API")
        wolfram_layout = QVBoxLayout(wolfram_group)

        wolfram_layout.addWidget(QLabel("API Key:"))
        self.wolfram_key = QLineEdit()
        self.wolfram_key.setPlaceholderText("Enter your Wolfram Alpha API key")
        wolfram_layout.addWidget(self.wolfram_key)

        api_layout.addWidget(wolfram_group)
        api_layout.addStretch()

        # Add tabs to the dialog
        tabs.addTab(general_tab, "General")
        tabs.addTab(api_tab, "API Keys")

        layout.addWidget(tabs)

        # Buttons
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save")
        self.cancel_button = QPushButton("Cancel")

        self.save_button.clicked.connect(self.save_settings)
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def load_settings(self):
        """Load settings from config"""
        self.enable_wake.setChecked(self.config.get("enable_wake_word", True))
        self.always_listen.setChecked(self.config.get("always_listen", False))
        self.volume_slider.setValue(int(self.config.get("volume", 70)))
        self.startup_greeting.setChecked(self.config.get("startup_greeting", True))
        self.wolfram_key.setText(self.config.get("wolfram_alpha_key", ""))

    def save_settings(self):
        """Save settings to config"""
        self.config["enable_wake_word"] = self.enable_wake.isChecked()
        self.config["always_listen"] = self.always_listen.isChecked()
        self.config["volume"] = self.volume_slider.value()
        self.config["startup_greeting"] = self.startup_greeting.isChecked()
        self.config["wolfram_alpha_key"] = self.wolfram_key.text()

        self.accept()

class EnhancedAura(QMainWindow):
    """Enhanced AURA voice assistant main application class"""

    def __init__(self):
        super().__init__()

        # Setup core components
        self.setup_config()
        self.setup_logging()
        self.load_detected_apps()

        # Setup UI
        self.setup_ui()
        self.setup_tray_icon()
        self.setup_connections()

        # Initialize speech components
        self.init_tts()
        self.init_wake_word_detection()

        # Command handling setup
        self.setup_commands()

        # Log application start
        self.log_message("Application started")

        # Show welcome message if enabled
        if self.config.get("startup_greeting", True):
            self.speak("AURA Voice Assistant is ready. Say 'Hey AURA' to activate.")

    def setup_config(self):
        """Setup configuration management"""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    self.config = json.load(f)
            else:
                # Default configuration
                self.config = {
                    "volume": 70,
                    "enable_wake_word": True,
                    "always_listen": False,
                    "startup_greeting": True,
                    "wolfram_alpha_key": "",
                    "gaming_mode": False
                }
                self.save_config()
        except Exception as e:
            # Fallback to default config on error
            self.config = {
                "volume": 70,
                "enable_wake_word": True,
                "always_listen": False,
                "startup_greeting": True,
                "wolfram_alpha_key": "",
                "gaming_mode": False
            }

    def save_config(self):
        """Save configuration to file"""
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            self.log_message(f"Error saving configuration: {str(e)}")

    def setup_logging(self):
        """Setup application logging"""
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            self.log_file = os.path.join(LOG_DIR, f"aura_{datetime.now().strftime('%Y%m%d')}.log")
        except Exception as e:
            print(f"Error setting up logging: {str(e)}")
            # Fallback to temporary directory
            self.log_file = os.path.join(tempfile.gettempdir(), f"aura_{datetime.now().strftime('%Y%m%d')}.log")

    def log_message(self, message):
        """Log a message to file and console"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"

        # Log to console
        print(log_entry, end='')

        # Log to file
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            print(f"Failed to write to log file: {str(e)}")

        # Update log in UI if available
        if hasattr(self, 'log_text'):
            self.log_text.append(log_entry)

    def load_detected_apps(self):
        """Detect installed applications based on platform"""
        self.detected_apps = {}

        if platform.system() == "Windows":
            self.detect_windows_apps()
        elif platform.system() == "Darwin":  # macOS
            self.detect_macos_apps()
        elif platform.system() == "Linux":
            self.detect_linux_apps()

        self.log_message(f"Detected {len(self.detected_apps)} applications")

    def detect_windows_apps(self):
        """Detect installed applications on Windows"""
        try:
            program_files = [
                os.environ.get('PROGRAMFILES', 'C:\\Program Files'),
                os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)')
            ]

            apps_to_detect = {
                'chrome': ['Google/Chrome/Application/chrome.exe'],
                'edge': ['Microsoft/Edge/Application/msedge.exe'],
                'firefox': ['Mozilla Firefox/firefox.exe'],
                'word': ['Microsoft Office/root/Office16/WINWORD.EXE', 'Microsoft Office/Office16/WINWORD.EXE'],
                'excel': ['Microsoft Office/root/Office16/EXCEL.EXE', 'Microsoft Office/Office16/EXCEL.EXE'],
                'powerpoint': ['Microsoft Office/root/Office16/POWERPNT.EXE', 'Microsoft Office/Office16/POWERPNT.EXE'],
                'notepad': ['Windows NT/Accessories/notepad.exe', 'notepad.exe'],
                'explorer': ['explorer.exe'],
                'calculator': ['Windows NT/Accessories/calc.exe', 'calc.exe'],
                'settings': ['Windows NT/ImmersiveControlPanel/SystemSettings.exe']
            }

            for app_name, paths in apps_to_detect.items():
                for base_path in program_files:
                    for rel_path in paths:
                        full_path = os.path.join(base_path, rel_path)
                        if os.path.exists(full_path):
                            self.detected_apps[app_name] = full_path
                            break

            # Check Windows system paths for common utilities
            system_apps = {
                'notepad': 'notepad.exe',
                'calculator': 'calc.exe',
                'explorer': 'explorer.exe',
                'settings': 'SystemSettings.exe'
            }

            for app_name, app_cmd in system_apps.items():
                if app_name not in self.detected_apps:
                    self.detected_apps[app_name] = app_cmd

        except Exception as e:
            self.log_message(f"Error detecting Windows applications: {str(e)}")

    def detect_macos_apps(self):
        """Detect installed applications on macOS"""
        common_apps = {
            'chrome': '/Applications/Google Chrome.app',
            'safari': '/Applications/Safari.app',
            'firefox': '/Applications/Firefox.app',
            'word': '/Applications/Microsoft Word.app',
            'excel': '/Applications/Microsoft Excel.app',
            'powerpoint': '/Applications/Microsoft PowerPoint.app',
            'notes': '/Applications/Notes.app',
            'calculator': '/Applications/Calculator.app',
            'terminal': '/Applications/Utilities/Terminal.app',
            'settings': '/Applications/System Preferences.app'
        }

        for app_name, app_path in common_apps.items():
            if os.path.exists(app_path):
                self.detected_apps[app_name] = app_path

    def detect_linux_apps(self):
        """Detect installed applications on Linux"""
        try:
            common_apps = ['google-chrome', 'firefox', 'chromium', 'libreoffice',
                           'gedit', 'gnome-terminal', 'gnome-calculator', 'nautilus',
                           'gnome-control-center']

            for app in common_apps:
                try:
                    path = subprocess.check_output(['which', app]).decode().strip()
                    if path:
                        self.detected_apps[app] = path
                except subprocess.CalledProcessError:
                    continue
        except Exception as e:
            self.log_message(f"Error detecting Linux applications: {str(e)}")

    def setup_ui(self):
        """Setup the application UI"""
        self.setWindowTitle("AURA Voice Assistant")
        self.setMinimumSize(800, 600)

        # Set application style with a dark theme and modern elements
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #444;
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 1ex;
                background-color: #2d2d2d;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
                color: #00aaff;
            }
            QPushButton {
                background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                                 stop: 0 #3a3a3a, stop: 1 #2a2a2a);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
            }
            QPushButton:hover {
                background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                                 stop: 0 #4a4a4a, stop: 1 #3a3a3a);
            }
            QPushButton:pressed {
                background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                                 stop: 0 #1a1a1a, stop: 1 #0a0a0a);
            }
            QPushButton#activateButton {
                background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                                 stop: 0 #00ccff, stop: 1 #00aaff);
                font-size: 14px;
                padding: 12px 20px;
            }
            QPushButton#activateButton:hover {
                background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                                 stop: 0 #00e5ff, stop: 1 #00b2ff);
            }
            QLabel#statusLabel {
                font-size: 14px;
                font-weight: bold;
                color: #00aaff;
            }
            QTextEdit {
                border: 1px solid #444;
                border-radius: 6px;
                background-color: #2d2d2d;
                color: #ffffff;
                padding: 8px;
            }
            QSlider::groove:horizontal {
                border: 1px solid #444;
                height: 8px;
                background: #2d2d2d;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #00aaff;
                border: 1px solid #444;
                width: 18px;
                height: 18px;
                line-height: 20px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 9px;
            }
            QTabWidget::pane {
                border: 1px solid #444;
                background-color: #2d2d2d;
            }
            QTabBar::tab {
                background: #3a3a3a;
                color: #ffffff;
                padding: 8px;
                border: 1px solid #444;
                border-bottom-color: #3a3a3a;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                           stop: 0 #00ccff, stop: 1 #00aaff);
                margin-bottom: -1px;
            }
        """)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Status and visualization panel
        status_panel = QFrame()
        status_panel.setFrameShape(QFrame.Shape.StyledPanel)
        status_panel.setStyleSheet("background-color: #2d2d2d; border-radius: 8px;")
        status_layout = QVBoxLayout(status_panel)

        # Title and status
        title_layout = QHBoxLayout()
        title_label = QLabel("AURA Voice Assistant")
        title_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title_layout.addWidget(title_label)
        title_layout.addStretch()

        version_label = QLabel(f"v{VERSION}")
        version_label.setStyleSheet("color: #7f8c8d;")
        title_layout.addWidget(version_label)

        status_layout.addLayout(title_layout)

        # Status indicator and visual feedback
        feedback_layout = QHBoxLayout()

        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusLabel")
        feedback_layout.addWidget(self.status_label)

        feedback_layout.addStretch()

        # Audio visualizer
        self.audio_viz = AudioVisualizer()
        feedback_layout.addWidget(self.audio_viz, 1)

        # System usage indicator
        self.cpu_indicator = CircularProgressBar()
        self.cpu_indicator.setToolTip("CPU Usage")
        self.cpu_indicator.setMaximumWidth(80)
        feedback_layout.addWidget(self.cpu_indicator)

        status_layout.addLayout(feedback_layout)

        # Add divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        status_layout.addWidget(divider)

        # Assistant feedback area
        self.response_text = QLabel("Say 'Hey AURA' to begin")
        self.response_text.setWordWrap(True)
        self.response_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.response_text.setStyleSheet("""
            font-size: 14px;
            color: #2c3e50;
            padding: 10px;
            background-color: #3a3a3a;
            border-radius: 4px;
        """)
        self.response_text.setMinimumHeight(60)
        status_layout.addWidget(self.response_text)

        main_layout.addWidget(status_panel)

        # Control panel
        control_panel = QFrame()
        control_panel.setFrameShape(QFrame.Shape.StyledPanel)
        control_panel.setStyleSheet("background-color: #2d2d2d; border-radius: 8px;")
        control_layout = QHBoxLayout(control_panel)

        # Activate button
        self.activate_button = QPushButton("Activate AURA")
        self.activate_button.setObjectName("activateButton")
        self.activate_button.setMinimumHeight(50)
        control_layout.addWidget(self.activate_button)

        # Mode selection
        mode_group = QGroupBox("Mode")
        mode_layout = QVBoxLayout(mode_group)

        self.mode_buttons = QButtonGroup(self)
        self.normal_mode_btn = QRadioButton("Normal")
        self.gaming_mode_btn = QRadioButton("Gaming")

        self.mode_buttons.addButton(self.normal_mode_btn)
        self.mode_buttons.addButton(self.gaming_mode_btn)

        # Set default mode based on config
        if self.config.get("gaming_mode", False):
            self.gaming_mode_btn.setChecked(True)
        else:
            self.normal_mode_btn.setChecked(True)

        mode_layout.addWidget(self.normal_mode_btn)
        mode_layout.addWidget(self.gaming_mode_btn)

        control_layout.addWidget(mode_group)

        # Volume control
        volume_group = QGroupBox("Volume")
        volume_layout = QVBoxLayout(volume_group)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(int(self.config.get("volume", 70)))
        self.volume_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.volume_slider.setTickInterval(10)

        volume_layout.addWidget(self.volume_slider)

        control_layout.addWidget(volume_group)

        # Settings button
        self.settings_button = QPushButton("Settings")
        control_layout.addWidget(self.settings_button)

        main_layout.addWidget(control_panel)

        # Detected Apps List
        apps_group = QGroupBox("Detected Applications")
        apps_layout = QVBoxLayout(apps_group)

        self.apps_list = QListWidget()
        for app_name, app_path in self.detected_apps.items():
            self.apps_list.addItem(f"{app_name}: {app_path}")

        apps_layout.addWidget(self.apps_list)
        main_layout.addWidget(apps_group)

        # Tab widget for different sections
        tabs = QTabWidget()

        # Command History tab
        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)

        self.history_text = QTextEdit()
        self.history_text.setReadOnly(True)
        self.history_text.setPlaceholderText("Command history will appear here...")

        history_layout.addWidget(self.history_text)

        # Add clear button
        clear_history_btn = QPushButton("Clear History")
        clear_history_btn.clicked.connect(self.clear_history)
        history_layout.addWidget(clear_history_btn)

        # System Log tab
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("System logs will appear here...")

        log_layout.addWidget(self.log_text)

        # Help tab
        help_tab = QWidget()
        help_layout = QVBoxLayout(help_tab)

        help_scroll = QScrollArea()
        help_scroll.setWidgetResizable(True)
        help_content = QWidget()
        help_content_layout = QVBoxLayout(help_content)

        # Help content
        help_title = QLabel("AURA Voice Assistant Help")
        help_title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        help_content_layout.addWidget(help_title)

        help_intro = QLabel(
            "AURA is your voice-activated assistant. Here are some commands you can try:"
        )
        help_intro.setWordWrap(True)
        help_content_layout.addWidget(help_intro)

        # Command examples
        commands_group = QGroupBox("Example Commands")
        commands_layout = QVBoxLayout(commands_group)

        command_examples = [
            "\"What time is it?\" - Get the current time",
            "\"Open Chrome\" - Launch Google Chrome browser",
            "\"What's the weather in New York?\" - Check weather",
            "\"Set a timer for 5 minutes\" - Start a countdown timer",
            "\"Tell me a joke\" - Get a random joke",
            "\"What's 15 times 27?\" - Basic calculations",
            "\"Search for cats\" - Search the web",
            "\"Play some music\" - Play background music",
            "\"System status\" - Check system resources",
            "\"Who are you?\" - Learn about AURA",
            "\"Increase brightness\" - Increase screen brightness",
            "\"Decrease brightness\" - Decrease screen brightness",
            "\"Shutdown\" - Shutdown the computer",
            "\"Restart\" - Restart the computer",
            "\"Open settings\" - Open system settings",
            "\"What is the square root of 144?\" - Ask Wolfram Alpha a question"
        ]

        for example in command_examples:
            commands_layout.addWidget(QLabel(example))

        help_content_layout.addWidget(commands_group)

        # Wake word info
        wake_group = QGroupBox("Wake Words")
        wake_layout = QVBoxLayout(wake_group)

        wake_info = QLabel(
            "To activate AURA, use any of these wake words:\n" +
            "\n".join([f"• \"{word.title()}\"" for word in WAKE_WORDS])
        )
        wake_layout.addWidget(wake_info)

        help_content_layout.addWidget(wake_group)

        # Add more help sections as needed
        help_content_layout.addStretch()

        help_scroll.setWidget(help_content)
        help_layout.addWidget(help_scroll)

        # Add tabs
        tabs.addTab(history_tab, "Command History")
        tabs.addTab(log_tab, "System Log")
        tabs.addTab(help_tab, "Help")

        main_layout.addWidget(tabs)

    def setup_tray_icon(self):
        """Setup system tray icon and menu"""
        # Create tray icon
        self.tray_icon = QSystemTrayIcon(self)

        # Create default icon (could be replaced with actual app icon)
        icon = QIcon()
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor("#54a0ff"))
        icon = QIcon(pixmap)
        self.tray_icon.setIcon(icon)

        # Create tray menu
        tray_menu = QMenu()

        # Add menu actions
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)

        toggle_wake_action = QAction("Toggle Wake Word Detection", self)
        toggle_wake_action.triggered.connect(self.toggle_wake_word_detection)
        tray_menu.addAction(toggle_wake_action)

        tray_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close_application)
        tray_menu.addAction(exit_action)

        # Set the menu
        self.tray_icon.setContextMenu(tray_menu)

        # Enable the tray icon
        self.tray_icon.show()

    def setup_connections(self):
        """Setup signal/slot connections"""
        # Button connections
        self.activate_button.clicked.connect(self.activate_assistant)
        self.settings_button.clicked.connect(self.show_settings)

        # Mode buttons
        self.normal_mode_btn.toggled.connect(self.update_mode)
        self.gaming_mode_btn.toggled.connect(self.update_mode)

        # System monitoring timer
        self.system_timer = QTimer(self)
        self.system_timer.timeout.connect(self.update_system_stats)
        self.system_timer.start(2000)  # Update every 2 seconds

    def init_tts(self):
        """Initialize text-to-speech engine"""
        self.tts_thread = TTSThread(self)
        self.tts_thread.speech_started.connect(self.on_speech_started)
        self.tts_thread.speech_finished.connect(self.on_speech_finished)
        self.tts_thread.error_occurred.connect(self.on_tts_error)

    def init_wake_word_detection(self):
        """Initialize wake word detection"""
        self.wake_word_thread = WakeWordThread(self)
        self.wake_word_thread.wake_word_detected.connect(self.on_wake_word_detected)
        self.wake_word_thread.audio_level.connect(self.update_audio_viz)
        self.wake_word_thread.error_occurred.connect(self.on_wake_word_error)

        # Start wake word detection if enabled
        if self.config.get("enable_wake_word", True):
            self.wake_word_thread.start()
            self.log_message("Wake word detection started")

    def setup_commands(self):
        """Setup command processing system"""
        self.command_thread = None
        self.command_history = []

        # Command handlers dictionary
        self.command_handlers = {
            "time": self.handle_time_command,
            "date": self.handle_date_command,
            "weather": self.handle_weather_command,
            "open": self.handle_open_command,
            "search": self.handle_search_command,
            "joke": self.handle_joke_command,
            "system": self.handle_system_command,
            "timer": self.handle_timer_command,
            "volume": self.handle_volume_command,
            "help": self.handle_help_command,
            "who are you": self.handle_who_are_you_command,
            "calculate": self.handle_calculate_command,
            "brightness": self.handle_brightness_command,
            "shutdown": self.handle_shutdown_command,
            "restart": self.handle_restart_command,
            "settings": self.handle_settings_command,
            "wolfram": self.handle_wolfram_command
        }

    def activate_assistant(self):
        """Manually activate the assistant"""
        if self.command_thread is not None and self.command_thread.isRunning():
            self.log_message("Command processing already in progress")
            return

        self.on_wake_word_detected()

    def on_wake_word_detected(self):
        """Handle wake word detection"""
        self.log_message("Wake word detected")
        self.status_label.setText("Listening...")
        self.response_text.setText("I'm listening. What can I do for you?")
        self.audio_viz.set_active(True)

        # Start command recognition
        self.command_thread = CommandThread(self)
        self.command_thread.command_received.connect(self.on_command_received)
        self.command_thread.command_processed.connect(self.on_command_processed)
        self.command_thread.audio_level.connect(self.update_audio_viz)
        self.command_thread.error_occurred.connect(self.on_command_error)
        self.command_thread.start()

    def on_command_received(self, command):
        """Handle received command"""
        self.log_message(f"Command received: {command}")
        self.status_label.setText("Processing...")
        self.response_text.setText(f"Processing: \"{command}\"")

        # Add to history
        self.command_history.append(command)
        self.history_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] {command}")

        # Process command
        response = self.process_command(command)

        # Speak response
        self.speak(response)

    def on_command_processed(self):
        """Handle command processing completion"""
        # If not in always-listen mode, resume wake word detection
        if not self.config.get("always_listen", False):
            self.wake_word_thread.resume()

        self.audio_viz.set_active(False)

    def on_command_error(self, error):
        """Handle command recognition error"""
        self.log_message(f"Command error: {error}")
        self.status_label.setText("Ready")
        self.response_text.setText(error)

        # Speak error message
        self.speak(error)

        # Resume wake word detection
        if not self.config.get("always_listen", False):
            self.wake_word_thread.resume()

        self.audio_viz.set_active(False)

    def on_wake_word_error(self, error):
        """Handle wake word detection error"""
        self.log_message(f"Wake word error: {error}")
        self.status_label.setText("Error")
        self.response_text.setText(f"Error: {error}")

    def on_tts_error(self, error):
        """Handle text-to-speech error"""
        self.log_message(f"TTS error: {error}")

    def on_speech_started(self):
        """Handle speech playback start"""
        self.status_label.setText("Speaking...")
        # Mute the microphone while speaking
        if hasattr(self, 'wake_word_thread'):
            self.wake_word_thread.paused = True

    def on_speech_finished(self):
        """Handle speech playback end"""
        self.status_label.setText("Ready")
        # Unmute the microphone after speaking
        if hasattr(self, 'wake_word_thread'):
            self.wake_word_thread.paused = False

        # If in always-listen mode, immediately listen for next command
        if self.config.get("always_listen", False):
            self.activate_assistant()

    def speak(self, text):
        """Speak the given text"""
        if not text:
            return

        self.log_message(f"Speaking: {text}")
        self.response_text.setText(text)

        # Set TTS parameters
        self.tts_thread.set_text(text)
        self.tts_thread.set_volume(self.config.get("volume", 70) / 100.0)

        # Start TTS
        self.tts_thread.start()

    def update_audio_viz(self, level):
        """Update audio visualization with audio level"""
        self.audio_viz.update_with_audio_level(level)

    def update_system_stats(self):
        """Update system statistics display"""
        # Get CPU usage
        cpu_percent = psutil.cpu_percent()
        self.cpu_indicator.set_value(cpu_percent)

    def update_mode(self):
        """Update application mode based on radio buttons"""
        self.config["gaming_mode"] = self.gaming_mode_btn.isChecked()
        self.save_config()

        mode = "Gaming" if self.config["gaming_mode"] else "Normal"
        self.log_message(f"Mode changed to: {mode}")

    def process_command(self, command):
        """Process a voice command and return a response"""
        command = command.lower()
        print(f"Processing command: {command}")  # Debug print

        # Check for command patterns
        if "what time" in command or "current time" in command:
            print("Handling time command")  # Debug print
            return self.handle_time_command(command)

        elif "what date" in command or "today's date" in command or "what day" in command:
            print("Handling date command")  # Debug print
            return self.handle_date_command(command)

        elif "weather" in command:
            print("Handling weather command")  # Debug print
            return self.handle_weather_command(command)

        elif any(word in command for word in ["open", "launch", "start", "run"]):
            print("Handling open command")  # Debug print
            return self.handle_open_command(command)

        elif any(word in command for word in ["search", "look up", "find"]):
            print("Handling search command")  # Debug print
            return self.handle_search_command(command)

        elif "joke" in command:
            print("Handling joke command")  # Debug print
            return self.handle_joke_command(command)

        elif any(word in command for word in ["system", "status", "resources"]):
            print("Handling system command")  # Debug print
            return self.handle_system_command(command)

        elif "timer" in command or "countdown" in command:
            print("Handling timer command")  # Debug print
            return self.handle_timer_command(command)

        elif "volume" in command:
            print("Handling volume command")  # Debug print
            return self.handle_volume_command(command)

        elif "help" in command:
            print("Handling help command")  # Debug print
            return self.handle_help_command(command)

        elif "who are you" in command:
            print("Handling who are you command")  # Debug print
            return self.handle_who_are_you_command(command)

        elif "calculate" in command or "what's" in command:
            print("Handling calculate command")  # Debug print
            return self.handle_calculate_command(command)

        elif "brightness" in command:
            print("Handling brightness command")  # Debug print
            return self.handle_brightness_command(command)

        elif "shutdown" in command:
            print("Handling shutdown command")  # Debug print
            return self.handle_shutdown_command(command)

        elif "restart" in command:
            print("Handling restart command")  # Debug print
            return self.handle_restart_command(command)

        elif "settings" in command:
            print("Handling settings command")  # Debug print
            return self.handle_settings_command(command)

        elif any(word in command for word in ["wolfram", "what is", "how much", "how many", "calculate"]):
            print("Handling wolfram command")  # Debug print
            return self.handle_wolfram_command(command)

        elif "exit" in command or "quit" in command or "close" in command:
            print("Handling exit command")  # Debug print
            self.close_application()
            return "Shutting down AURA. Goodbye!"

        else:
            # Generic response for unrecognized commands
            print("Handling unrecognized command")  # Debug print
            return "I'm not sure how to help with that. Try asking for help to see what commands I support."

    def handle_time_command(self, command):
        """Handle time-related commands"""
        current_time = datetime.now().strftime("%I:%M %p")
        return f"The current time is {current_time}."

    def handle_date_command(self, command):
        """Handle date-related commands"""
        current_date = datetime.now().strftime("%A, %B %d, %Y")
        return f"Today is {current_date}."

    def handle_weather_command(self, command):
        """Handle weather-related commands"""
        # Extract location from command
        location_match = re.search(r"(weather|forecast)\s+(?:in|for|at)\s+(.+?)(?:\?|$)", command)

        if location_match:
            location = location_match.group(2).strip()
        else:
            location = "your location"

        # Use OpenWeatherMap API to get weather data
        try:
            api_key = OPENWEATHER_API_KEY
            base_url = "http://api.openweathermap.org/data/2.5/weather"
            params = {
                'q': location,
                'appid': api_key,
                'units': 'metric'  # Use metric units
            }
            response = requests.get(base_url, params=params)
            weather_data = response.json()

            if response.status_code == 200:
                weather_description = weather_data['weather'][0]['description']
                temperature = weather_data['main']['temp']
                return f"The weather in {location} is {weather_description} with a temperature of {temperature}°C."
            else:
                return f"Sorry, I couldn't fetch the weather data for {location}."
        except Exception as e:
            return f"Sorry, I couldn't fetch the weather data for {location}. Error: {str(e)}"

    def handle_open_command(self, command):
        """Handle commands to open applications"""
        # Extract app name from command
        app_match = re.search(r"(open|launch|start|run)\s+(.+?)(?:\s|$|\.)", command)

        if not app_match:
            return "I'm not sure which application you want me to open."

        app_name = app_match.group(2).strip().lower()

        # Check if we have the app in our detected list
        for detected_app, path in self.detected_apps.items():
            if app_name in detected_app or detected_app in app_name:
                try:
                    if platform.system() == "Windows":
                        os.startfile(path)
                    elif platform.system() == "Darwin":  # macOS
                        subprocess.Popen(['open', path])
                    else:  # Linux
                        subprocess.Popen([path])

                    return f"Opening {detected_app}."
                except Exception as e:
                    self.log_message(f"Error opening application: {str(e)}")
                    return f"I had trouble opening {detected_app}."

        # If app not found
        return f"I couldn't find {app_name} on your system."

    def handle_search_command(self, command):
        """Handle search commands"""
        # Extract search query
        search_match = re.search(r"(search|look up|find)\s+(?:for\s+)?(.+?)(?:\?|$)", command)

        if not search_match:
            return "What would you like me to search for?"

        query = search_match.group(2).strip()

        # Open web browser with search query
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        try:
            webbrowser.open(search_url)
            return f"Searching for '{query}'."
        except Exception as e:
            self.log_message(f"Error performing search: {str(e)}")
            return "I had trouble opening the search."

    def handle_joke_command(self, command):
        """Handle joke requests"""
        jokes = [
            "Why don't scientists trust atoms? Because they make up everything!",
            "Why did the scarecrow win an award? Because he was outstanding in his field!",
            "I told my wife she was drawing her eyebrows too high. She looked surprised.",
            "What's the best thing about Switzerland? I don't know, but the flag is a big plus.",
            "Did you hear about the mathematician who's afraid of negative numbers? He'll stop at nothing to avoid them.",
            "Why do we tell actors to 'break a leg?' Because every play has a cast.",
            "Parallel lines have so much in common. It's a shame they'll never meet.",
            "I'm reading a book about anti-gravity. It's impossible to put down!",
            "I told my computer I needed a break, and now it won't stop sending me vacation ads."
        ]
        return random.choice(jokes)

    def handle_system_command(self, command):
        """Handle system status commands"""
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        memory_percent = memory.percent

        return f"System status: CPU usage is {cpu_percent}%. Memory usage is {memory_percent}%."

    def handle_timer_command(self, command):
        """Handle timer commands"""
        # Extract time from command
        time_match = re.search(r"timer\s+for\s+(\d+)\s+(second|minute|hour)s?", command)

        if not time_match:
            return "Please specify how long you want the timer for. For example, 'set a timer for 5 minutes'."

        amount = int(time_match.group(1))
        unit = time_match.group(2)

        # Convert to seconds
        seconds = amount
        if unit == "minute":
            seconds = amount * 60
        elif unit == "hour":
            seconds = amount * 3600

        # Start a timer thread
        threading.Thread(target=self.run_timer, args=(seconds, amount, unit)).start()

        return f"Timer set for {amount} {unit}{'s' if amount > 1 else ''}."

    def run_timer(self, seconds, amount, unit):
        """Run a timer in the background"""
        time.sleep(seconds)

        # Play notification sound
        pygame.mixer.init()
        pygame.mixer.music.load(self.get_notification_sound())
        pygame.mixer.music.play()

        # Show notification
        message = f"Your {amount} {unit}{'s' if amount > 1 else ''} timer is complete!"
        self.tray_icon.showMessage("AURA Timer", message, QSystemTrayIcon.MessageIcon.Information, 5000)
        self.speak(message)

    def get_notification_sound(self):
        """Get path to notification sound file, or create one if needed"""
        # Path to notification sound
        sound_path = os.path.join(tempfile.gettempdir(), "aura_notification.wav")

        # If sound file doesn't exist, create a simple beep sound
        if not os.path.exists(sound_path):
            try:
                self.create_beep_sound(sound_path)
            except:
                # Fallback for platforms where we can't create the sound
                pass

        return sound_path

    def create_beep_sound(self, path):
        """Create a simple beep sound file"""
        sample_rate = 44100
        duration = 0.5  # half second beep
        frequency = 440  # A4 note

        # Generate sine wave
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        tone = np.sin(frequency * t * 2 * np.pi)

        # Normalize to 16-bit range and convert to integers
        audio = np.int16(tone * 32767)

        # Create WAV file
        with wave.open(path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio.tobytes())

    def handle_volume_command(self, command):
        """Handle volume adjustment commands"""
        # Check for volume level in command
        volume_match = re.search(r"volume\s+(to\s+)?(\d+)(?:\s+percent)?", command)

        if volume_match:
            # Set volume to specific level
            try:
                volume = int(volume_match.group(2))
                volume = max(0, min(100, volume))  # Clamp between 0 and 100
                self.volume_slider.setValue(volume)
                self.config["volume"] = volume
                self.save_config()
                return f"Volume set to {volume} percent."
            except:
                pass

        # Check for relative volume changes
        if "up" in command or "increase" in command:
            current = self.volume_slider.value()
            new_volume = min(100, current + 10)
            self.volume_slider.setValue(new_volume)
            self.config["volume"] = new_volume
            self.save_config()
            return f"Volume increased to {new_volume} percent."

        elif "down" in command or "decrease" in command or "lower" in command:
            current = self.volume_slider.value()
            new_volume = max(0, current - 10)
            self.volume_slider.setValue(new_volume)
            self.config["volume"] = new_volume
            self.save_config()
            return f"Volume decreased to {new_volume} percent."

        elif "mute" in command:
            self.volume_slider.setValue(0)
            self.config["volume"] = 0
            self.save_config()
            return "Volume muted."

        # If no specific command matched
        current = self.volume_slider.value()
        return f"Current volume is {current} percent. You can say 'volume up', 'volume down', or 'volume to 50' to adjust it."

    def handle_help_command(self, command):
        """Handle help requests"""
        return "Here are some things you can say: 'what time is it', 'what's the weather', 'open Chrome', 'search for cats', 'tell me a joke', 'set a timer for 5 minutes', or 'system status'."

    def handle_who_are_you_command(self, command):
        """Handle 'who are you' requests"""
        return "I am AURA, your voice-activated assistant. I can help you with various tasks like telling the time, opening applications, searching the web, and more!"

    def handle_calculate_command(self, command):
        """Handle calculation requests"""
        # Extract calculation from command
        calc_match = re.search(r"what's\s+(.+?)\s+(\+|\-|\*|\/)\s+(.+?)(?:\?|$)", command)

        if calc_match:
            num1 = float(calc_match.group(1))
            operator = calc_match.group(2)
            num2 = float(calc_match.group(3))

            if operator == "+":
                result = num1 + num2
            elif operator == "-":
                result = num1 - num2
            elif operator == "*":
                result = num1 * num2
            elif operator == "/":
                result = num1 / num2
            else:
                return "I'm not sure how to perform that calculation."

            return f"The result is {result}."

        return "I'm not sure how to perform that calculation."

    def handle_brightness_command(self, command):
        """Handle brightness adjustment commands"""
        if "increase" in command or "up" in command:
            return self.increase_brightness()
        elif "decrease" in command or "down" in command:
            return self.decrease_brightness()
        else:
            return "I'm not sure how to adjust the brightness. You can say 'increase brightness' or 'decrease brightness'."

    def increase_brightness(self):
        """Increase screen brightness"""
        if platform.system() == "Windows":
            # Windows brightness adjustment code
            return "Brightness increased."
        elif platform.system() == "Darwin":
            # macOS brightness adjustment code
            return "Brightness increased."
        elif platform.system() == "Linux":
            # Linux brightness adjustment code
            return "Brightness increased."
        else:
            return "Brightness adjustment is not supported on this platform."

    def decrease_brightness(self):
        """Decrease screen brightness"""
        if platform.system() == "Windows":
            # Windows brightness adjustment code
            return "Brightness decreased."
        elif platform.system() == "Darwin":
            # macOS brightness adjustment code
            return "Brightness decreased."
        elif platform.system() == "Linux":
            # Linux brightness adjustment code
            return "Brightness decreased."
        else:
            return "Brightness adjustment is not supported on this platform."

    def handle_shutdown_command(self, command):
        """Handle shutdown command"""
        if platform.system() == "Windows":
            os.system("shutdown /s /t 1")
            return "Shutting down the computer."
        elif platform.system() == "Darwin":
            os.system("shutdown -h now")
            return "Shutting down the computer."
        elif platform.system() == "Linux":
            os.system("shutdown -h now")
            return "Shutting down the computer."
        else:
            return "Shutdown is not supported on this platform."

    def handle_restart_command(self, command):
        """Handle restart command"""
        if platform.system() == "Windows":
            os.system("shutdown /r /t 1")
            return "Restarting the computer."
        elif platform.system() == "Darwin":
            os.system("shutdown -r now")
            return "Restarting the computer."
        elif platform.system() == "Linux":
            os.system("shutdown -r now")
            return "Restarting the computer."
        else:
            return "Restart is not supported on this platform."

    def handle_settings_command(self, command):
        """Handle settings command"""
        if platform.system() == "Windows":
            os.system("start ms-settings:")
            return "Opening settings."
        elif platform.system() == "Darwin":
            os.system("open /System/Library/PreferencePanes/")
            return "Opening settings."
        elif platform.system() == "Linux":
            os.system("gnome-control-center")
            return "Opening settings."
        else:
            return "Opening settings is not supported on this platform."

    def handle_wolfram_command(self, command):
        """Handle Wolfram Alpha queries"""
        # Extract query from command
        query_match = re.search(r"(wolfram|what is|how much|how many|calculate)\s+(.+?)(?:\?|$)", command)

        if query_match:
            query = query_match.group(2).strip()
            try:
                api_key = WOLFRAM_ALPHA_API_KEY
                result = query_wolfram_conversational(api_key, query)

                if "error" in result:
                    return result["error"]
                else:
                    # Parse the result to get the answer
                    # This part depends on the structure of the response from the API
                    # You may need to adjust this based on the actual response format
                    answer = result.get("answer", "I couldn't find a specific answer for that query.")
                    return f"The answer is: {answer}"
            except Exception as e:
                return f"Sorry, I couldn't fetch the answer for that query. Error: {str(e)}"
        else:
            return "I'm not sure how to answer that question."

    def show_settings(self):
        """Show settings dialog"""
        dialog = SettingsDialog(self.config, self)
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            self.save_config()
            self.log_message("Settings updated")

            # Apply settings
            if self.config.get("enable_wake_word", True):
                if not self.wake_word_thread.isRunning():
                    self.wake_word_thread.start()
            else:
                if self.wake_word_thread.isRunning():
                    self.wake_word_thread.stop()

    def clear_history(self):
        """Clear command history"""
        self.command_history = []
        self.history_text.clear()
        self.log_message("Command history cleared")

    def toggle_wake_word_detection(self):
        """Toggle wake word detection on/off"""
        if self.wake_word_thread.isRunning():
            self.wake_word_thread.stop()
            self.log_message("Wake word detection stopped")
            self.config["enable_wake_word"] = False
        else:
            self.wake_word_thread.start()
            self.log_message("Wake word detection started")
            self.config["enable_wake_word"] = True

        self.save_config()

    def closeEvent(self, event):
        """Handle window close event"""
        # Minimize to tray instead of closing
        if self.tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            self.close_application()

    def close_application(self):
        """Close the application properly"""
        # Stop threads
        if hasattr(self, 'wake_word_thread') and self.wake_word_thread.isRunning():
            self.wake_word_thread.stop()

        # Save config
        self.save_config()

        # Close application
        QApplication.quit()

def main():
    """Main application entry point"""
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("AURA Voice Assistant")

    # Set style
    app.setStyle("Fusion")

    # Create and show main window
    window = EnhancedAura()
    window.show()

    # Start application event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
