# CaptureSnap OCR

## Overview

CaptureSnap OCR is a simple tool designed to easily capture and extract text from your screen. It works by overlaying a resizable transparent window on your screen, which you can move and scale over the text you want to capture. The text within the designated area can then be captured and processed via OCR (Optical Character Recognition), and is instantly copied to your clipboard.

![image](https://github.com/Vwing/capturesnap-ocr/assets/9121881/0268693a-ad0d-4aa4-9b1b-dd32800c795c)

## Features

- A simple, user-friendly, and resizable GUI.
- OCR text capture from any part of the screen.
- Text from captured region is automatically copied to the clipboard.
- The last captured image and extracted text are saved to a .png and .txt file respectively.
- Choose between two OCR engines: Tesseract or the [MiniCPM-OCR 1.0](https://huggingface.co/openbmb/MiniCPM-OCR-1.0-gguf) vision model.

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

3. Pick an OCR engine from the dropdown next to the button. The app remembers your choice.

4. Click the "Capture OCR" button at the top of the window. The text within the area will be captured, processed by OCR, and copied to your clipboard.

5. You can find the screenshot and the extracted text as `screenshot.png` and `captured_text.txt` in the same directory as your script.

## OCR Engines

- **Tesseract**: fast and lightweight. It needs the Tesseract OCR software installed (see above).
- **MiniCPM-OCR**: a 1.3B-parameter vision-language OCR model. It is more accurate than Tesseract on small screen fonts, code indentation, and mixed English and Chinese text. It runs locally through [llama.cpp](https://github.com/ggml-org/llama.cpp)'s `llama-server`, on the GPU when one is available. It uses about 2 GB of video memory, and a capture takes well under a second on a modern GPU.

The model loads when you select MiniCPM-OCR, or when the app starts if MiniCPM-OCR was the engine you last used. It stays loaded until you close the window, even if you switch back to Tesseract. The status text next to the dropdown shows loading progress. If you capture before the model is ready, the text is read as soon as loading finishes. After the first run, loading takes a few seconds. The very first load can take up to a minute while the GPU driver compiles shaders.

The first time you select MiniCPM-OCR, the app downloads everything it needs into its own folder:

- `models/MiniCPM-OCR-1.0-gguf/`: the Q8_0 model and its vision projector (about 1.7 GB).
- `llama.cpp/`: the Windows Vulkan build of llama.cpp (about 37 MB), which runs on NVIDIA, AMD and Intel GPUs and falls back to the CPU. Not downloaded on Linux or macOS: install llama.cpp yourself and put `llama-server` on your PATH.

Interrupted downloads resume the next time you try. Server output is written to `llama-server.log`.

To use a different llama.cpp build, such as a CUDA build, set `llama_server_path` in `settings.json`:

```json
{
  "engine": "minicpm",
  "llama_server_path": "C:\\path\\to\\llama.cpp\\llama-server.exe"
}
```

## License

CaptureSnap OCR is open-source software licensed under the MIT license.

## Contact

For more information, questions or feedback, please feel free to open an issue on our GitHub page.

Please enjoy CaptureSnap OCR and let us know of any way we can improve your text capturing experience!

