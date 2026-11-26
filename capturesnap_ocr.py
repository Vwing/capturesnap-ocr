import pytesseract
from PIL import ImageGrab
import pygetwindow as gw
import pyrect
import pyperclip
import tkinter as tk
from tkinter import messagebox
import json
import os
import queue
import threading
import ctypes

from minicpm_ocr import MiniCPMOCR, MiniCPMLoadError

# Hide console window on Windows
if os.name == 'nt':
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(APP_DIR, 'settings.json')

# Dropdown label -> value saved in settings.json
ENGINES = {"Tesseract": "tesseract", "MiniCPM-OCR": "minicpm"}
DEFAULT_ENGINE = "tesseract"


def load_settings():
    try:
        with open(SETTINGS_PATH, encoding='utf-8') as f:
            settings = json.load(f)
    except (OSError, ValueError):
        return {}
    return settings if isinstance(settings, dict) else {}


def save_settings(settings):
    temp_path = SETTINGS_PATH + '.tmp'
    with open(temp_path, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)
    os.replace(temp_path, SETTINGS_PATH)


class OCRApp:
    def __init__(self, master):
        self.master = master
        self.master.title("CaptureSnap OCR")
        self.master.config(bg="#cccccc")
        self.master.attributes('-alpha', 0.5)
        self.master.geometry("400x120")
        self.master.attributes("-topmost", 1)

        # Bind mouse events to move the GUI
        self.master.bind('<Button-1>', self.start_move)
        self.master.bind('<B1-Motion>', self.on_move)

        self.settings = load_settings()
        self.engine = self.settings.get('engine')
        if self.engine not in ENGINES.values():
            self.engine = DEFAULT_ENGINE
        self.minicpm = None          # loaded on first selection, kept until the window closes
        self.minicpm_status = ""
        self.busy = False
        self.events = queue.Queue()  # results from background threads, handled on the Tk thread

        top_bar = tk.Frame(self.master, bg="#cccccc")
        top_bar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=4)

        # Button to start OCR
        self.start_button = tk.Button(top_bar, text="Capture OCR", command=self.capture_and_ocr, bg="#eeeeee")
        self.start_button.pack(side=tk.LEFT)

        # OCR engine dropdown
        self.engine_var = tk.StringVar(value=self.engine_label(self.engine))
        self.engine_menu = tk.OptionMenu(top_bar, self.engine_var, *ENGINES, command=self.on_engine_selected)
        self.engine_menu.config(bg="#eeeeee", highlightthickness=0)
        self.engine_menu.pack(side=tk.LEFT, padx=(6, 0))

        self.status_label = tk.Label(top_bar, text="", bg="#cccccc", anchor="w")
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))

        self.screenshot = None
        self.captured_text = None

        # Create a canvas for the white-bordered box
        self.canvas = tk.Canvas(self.master, bg="#cccccc", highlightthickness=2)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Configure the canvas border color
        self.canvas.config(highlightbackground="white")

        self.master.protocol("WM_DELETE_WINDOW", self.on_close)
        self.master.after(100, self.process_events)

        if self.engine == "minicpm":
            self.start_minicpm()
            self.set_status(self.minicpm_status)

    @staticmethod
    def engine_label(engine):
        return next(label for label, value in ENGINES.items() if value == engine)

    def on_engine_selected(self, label):
        engine = ENGINES[label]
        if engine == self.engine:
            return
        self.engine = engine
        self.settings['engine'] = engine
        if engine == "minicpm":
            self.start_minicpm()
            self.set_status(self.minicpm_status)
        else:
            self.set_status("")
        try:
            save_settings(self.settings)
        except OSError:
            self.set_status("Couldn't save settings.json")

    def start_minicpm(self):
        """Start loading MiniCPM-OCR; does nothing if it is loading or loaded, retries if it failed."""
        if self.minicpm is None:
            self.minicpm = MiniCPMOCR(APP_DIR, on_status=self.on_minicpm_status,
                                      llama_server_path=self.settings.get('llama_server_path'))
        if not (self.minicpm.loading or self.minicpm.ready):
            self.minicpm_status = "Starting MiniCPM-OCR…"
        self.minicpm.start()

    def on_minicpm_status(self, message, error=None):
        # Called from the MiniCPM loader thread.
        self.events.put(("minicpm_status", message, error))

    def process_events(self):
        try:
            while True:
                kind, *args = self.events.get_nowait()
                if kind == "minicpm_status":
                    message, error = args
                    self.minicpm_status = message
                    if self.engine == "minicpm":
                        self.set_status(message)
                        if error:
                            messagebox.showerror("MiniCPM-OCR", error, parent=self.master)
                elif kind == "ocr_done":
                    self.finish_ocr(*args)
                elif kind == "ocr_failed":
                    self.fail_ocr(*args)
        except queue.Empty:
            pass
        self.master.after(100, self.process_events)

    def set_status(self, text):
        self.status_label.config(text=text)

    def set_busy(self, busy):
        self.busy = busy
        self.start_button.config(state=tk.DISABLED if busy else tk.NORMAL)

    def capture_and_ocr(self):
        if self.busy:
            return
        engine = self.engine
        if engine == "minicpm":
            self.start_minicpm()  # restarts the model if it failed to load or stopped

        self.master.update()

        # Capture the area inside the white-bordered box
        left, upper = self.canvas.winfo_rootx(), self.canvas.winfo_rooty()
        right = left + self.canvas.winfo_width()
        lower = upper + self.canvas.winfo_height()

        rect = (left, upper, right, lower)

        # Make the window fully transparent during capture
        self.master.attributes('-alpha', 0.0)

        # Capture the screen within the window's rectangle, considering all monitors
        self.screenshot = ImageGrab.grab(rect, all_screens=True)

        # Restore window transparency
        self.master.attributes('-alpha', 0.5)

        # Run OCR in the background so the window stays responsive
        self.set_busy(True)
        if engine == "minicpm" and not self.minicpm.ready:
            self.set_status("Waiting for MiniCPM-OCR…")
        else:
            self.set_status("Reading text…")
        threading.Thread(target=self.run_ocr, args=(engine, self.screenshot), daemon=True).start()

    def run_ocr(self, engine, image):
        # Runs on a worker thread; results go back to the Tk thread through self.events.
        try:
            if engine == "minicpm":
                text = self.minicpm.ocr(image)
            else:
                text = pytesseract.image_to_string(image)
        except Exception as e:
            self.events.put(("ocr_failed", e))
        else:
            self.events.put(("ocr_done", image, text))

    def finish_ocr(self, image, text):
        self.captured_text = text

        # Save the screenshot as a .png file
        screenshot_path = os.path.join(APP_DIR, 'screenshot.png')
        image.save(screenshot_path)

        # Save the captured text as a .txt file
        text_path = os.path.join(APP_DIR, 'captured_text.txt')
        with open(text_path, 'w', encoding='utf-8') as text_file:
            text_file.write(text)

        # Copy the extracted text to the clipboard
        pyperclip.copy(text)

        self.set_busy(False)
        self.set_status("Copied to clipboard" if text.strip() else "No text found")

    def fail_ocr(self, error):
        self.set_busy(False)
        self.set_status("OCR failed")
        if not isinstance(error, MiniCPMLoadError):  # load failures were already shown
            messagebox.showerror("CaptureSnap OCR", f"OCR failed:\n{error}", parent=self.master)

    def on_close(self):
        if self.minicpm is not None:
            self.minicpm.close()
        self.master.destroy()

    def start_move(self, event):
        self.master.x = event.x
        self.master.y = event.y

    def on_move(self, event):
        deltax = event.x - self.master.x
        deltay = event.y - self.master.y
        x = self.master.winfo_x() + deltax
        y = self.master.winfo_y() + deltay
        self.master.geometry(f"+{x}+{y}")

def main():
    root = tk.Tk()
    app = OCRApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
