# CaptureSnap OCR

## Overview

CaptureSnap OCR is a simple tool designed to easily capture and extract text from your screen. It works by overlaying a resizable transparent window on your screen, which you can move and scale over the text you want to capture. The text within the designated area can then be captured and processed via OCR (Optical Character Recognition), and is instantly copied to your clipboard.

![image](https://github.com/Vwing/capturesnap-ocr/assets/9121881/0268693a-ad0d-4aa4-9b1b-dd32800c795c)

## Features

- A simple, user-friendly, and resizable GUI.
- OCR text capture from any part of the screen.
- Text from captured region is automatically copied to the clipboard.
- The last captured image and extracted text are saved to a .png and .txt file respectively.

## Installation & Dependencies

CaptureSnap OCR requires Python 3.7 or higher. You will also need to install the following Python packages:

- `pytesseract`
- `PIL`
- `pygetwindow`
- `pyrect`
- `pyperclip`
- `tkinter`

You can install these packages using pip:

```shell
pip install pytesseract pillow pygetwindow pyrect pyperclip tkinter
```

In addition to the Python dependencies, you also need to install the Tesseract OCR software. Please refer to [Tesseract's GitHub page](https://github.com/tesseract-ocr/tesseract) for instructions on how to install it on your specific operating system. Once Tesseract is installed, make sure it's in your system's PATH or the `pytesseract.pytesseract.tesseract_cmd` variable is set to the Tesseract path in the script.

## Usage

1. Run the script with Python:

```shell
python3 capturesnap_ocr.py
```

2. A transparent window will appear. Move and resize this window to overlay the text you want to capture.

3. Click the "Capture OCR" button at the top of the window. The text within the area will be captured, processed by OCR, and copied to your clipboard.

4. You can find the screenshot and the extracted text as `screenshot.png` and `captured_text.txt` in the same directory as your script.

## License

CaptureSnap OCR is open-source software licensed under the MIT license.

## Contact

For more information, questions or feedback, please feel free to open an issue on our GitHub page.

Please enjoy CaptureSnap OCR and let us know of any way we can improve your text capturing experience!


