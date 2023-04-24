import pytesseract
from PIL import ImageGrab
import pygetwindow as gw
import pyrect
import pyperclip
import tkinter as tk
import os
import ctypes

# Hide console window on Windows
if os.name == 'nt':
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

class OCRApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Simple OCR Tool")
        self.master.config(bg="#cccccc")
        self.master.attributes('-alpha', 0.5)
        self.master.geometry("400x120")
        self.master.attributes("-topmost", 1)

        # Bind mouse events to move the GUI
        self.master.bind('<Button-1>', self.start_move)
        self.master.bind('<B1-Motion>', self.on_move)

        # Button to start OCR
        self.start_button = tk.Button(self.master, text="Capture OCR", command=self.capture_and_ocr, bg="#eeeeee")
        self.start_button.pack(side=tk.TOP, pady=4)

        self.screenshot = None
        self.captured_text = None

        # Create a canvas for the white-bordered box
        self.canvas = tk.Canvas(self.master, bg="#cccccc", highlightthickness=2)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Configure the canvas border color
        self.canvas.config(highlightbackground="white")

    def capture_and_ocr(self):
        self.master.update()

        left, upper, width, height = self.master.winfo_rootx() + 10, self.master.winfo_rooty() + 35, self.master.winfo_width() - 20, self.master.winfo_height() - 45
        right = left + width
        lower = upper + height

        rect = (left, upper, right, lower)

        # Make the window fully transparent during capture
        self.master.attributes('-alpha', 0.0)
        
        # Capture the screen within the window's rectangle, considering all monitors
        self.screenshot = ImageGrab.grab(rect, all_screens=True)

        # Restore window transparency
        self.master.attributes('-alpha', 0.5)
        
        # Run OCR on the captured image
        self.captured_text = pytesseract.image_to_string(self.screenshot)

        # Save the screenshot as a .png file
        screenshot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'screenshot.png')
        self.screenshot.save(screenshot_path)

        # Save the captured text as a .txt file
        text_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'captured_text.txt')
        with open(text_path, 'w', encoding='utf-8') as text_file:
            text_file.write(self.captured_text)

        # Copy the extracted text to the clipboard
        pyperclip.copy(self.captured_text)
        
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