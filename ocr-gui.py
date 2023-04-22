import pytesseract
from PIL import ImageGrab
import pygetwindow as gw
import pyrect
import pyperclip
import tkinter as tk
import os

class OCRApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Simple OCR Tool")
        self.master.config(bg="#cccccc")
        self.master.attributes('-alpha', 0.15)
        self.master.geometry("400x120")

        # Button to start OCR
        self.start_button = tk.Button(self.master, text="Capture OCR", command=self.capture_and_ocr, bg="#eeeeee")
        self.start_button.pack(side=tk.TOP, pady=10)

        self.screenshot = None
        self.captured_text = None

    def capture_and_ocr(self):
        left, upper, width, height = self.master.winfo_rootx(), self.master.winfo_rooty(), self.master.winfo_width(), self.master.winfo_height()
        right = left + width
        lower = upper + height

        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()

        # Ensure the bounding box is within the screen dimensions
        left, upper = max(0, left), max(0, upper)
        right, lower = min(screen_width, right), min(screen_height, lower)

        if left >= right or upper >= lower:
            print("Invalid window dimensions for capture.")
            return

        rect = (left, upper, right, lower)

        # Capture the screen within the window's rectangle
        self.screenshot = ImageGrab.grab(rect)

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

def main():
    root = tk.Tk()
    app = OCRApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
