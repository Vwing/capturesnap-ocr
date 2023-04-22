import pytesseract
from PIL import ImageGrab
import pygetwindow as gw
import pyrect
import pyperclip
import os

# Configure the tesseract executable path
pytesseract.pytesseract.tesseract_cmd = r'tesseract.exe'

def capture_and_ocr(window_title):
    # Get the window's Rectangle object
    win = gw.getWindowsWithTitle(window_title)[0]
    rect = win._rect

    # Convert the Rect object to a tuple (left, top, right, bottom)
    bbox = (rect.left, rect.top, rect.right, rect.bottom)

    # Capture the screen within the window's rectangle
    screenshot = ImageGrab.grab(bbox)

    # Save the screenshot as a .png file
    screenshot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'screenshot.png')
    screenshot.save(screenshot_path)

    # Run OCR on the captured image
    text = pytesseract.image_to_string(screenshot)

    # Save the captured text as a .txt file
    text_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'captured_text.txt')
    with open(text_path, 'w', encoding='utf-8') as text_file:
        text_file.write(text)

    # Copy the extracted text to the clipboard
    pyperclip.copy(text)


def main():
    print("Please enter the title of the window you want to capture:")
    window_title = input().strip()

    # Check if the window exists
    if not gw.getWindowsWithTitle(window_title):
        print(f"Window '{window_title}' not found. Please make sure the title is correct.")
        return

    print(f"Press Enter to capture and copy the text from '{window_title}' to clipboard.")
    input()

    capture_and_ocr(window_title)

if __name__ == "__main__":
    main()