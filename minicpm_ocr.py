"""MiniCPM-OCR 1.0 (GGUF) engine.

Runs llama.cpp's ``llama-server`` as a child process with the model loaded and
sends each capture to its OpenAI-compatible chat endpoint. On first use the
model files (and, on Windows, a llama.cpp build) are downloaded next to the app.
"""

import base64
import io
import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
import zipfile

from PIL import Image

# Pinned llama.cpp release. The Vulkan build is small and runs on NVIDIA, AMD and
# Intel GPUs, falling back to the CPU when no GPU is usable.
LLAMA_CPP_BUILD = "b12751"
LLAMA_CPP_ASSET = f"llama-{LLAMA_CPP_BUILD}-bin-win-vulkan-x64.zip"
LLAMA_CPP_URL = f"https://github.com/ggml-org/llama.cpp/releases/download/{LLAMA_CPP_BUILD}/{LLAMA_CPP_ASSET}"

MODEL_REPO_URL = "https://huggingface.co/openbmb/MiniCPM-OCR-1.0-gguf/resolve/main"
MODEL_FILE = "MiniCPM-OCR-1_0-Q8_0.gguf"   # the model card's recommended quant
MMPROJ_FILE = "mmproj-model-f16-4x.gguf"   # vision projector, required for images

MODEL_ALIAS = "minicpm-ocr"
OCR_PROMPT = "Text Recognition:"
USER_AGENT = "capturesnap-ocr"

SERVER_START_TIMEOUT = 300  # seconds
OCR_TIMEOUT = 300           # seconds

# Requests to our own server must never go through a configured HTTP proxy.
_local_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class MiniCPMLoadError(RuntimeError):
    """The model could not be downloaded or started; the error was already reported via on_status."""


class MiniCPMOCR:
    def __init__(self, base_dir, on_status=None, llama_server_path=None):
        self.base_dir = base_dir
        self.llama_dir = os.path.join(base_dir, "llama.cpp")
        self.model_dir = os.path.join(base_dir, "models", "MiniCPM-OCR-1.0-gguf")
        self.log_path = os.path.join(base_dir, "llama-server.log")
        self.llama_server_path = llama_server_path
        # on_status(message, error=None) is called from a background thread.
        self._on_status = on_status or (lambda message, error=None: None)

        self._lock = threading.Lock()
        self._finished = threading.Event()  # set when a load attempt ends, ready or failed
        self._thread = None
        self._error = None
        self._proc = None
        self._job = None
        self._log = None
        self._url = None
        self._closed = False

    @property
    def loading(self):
        return self._thread is not None and not self._finished.is_set()

    @property
    def ready(self):
        proc = self._proc
        return self._finished.is_set() and self._error is None and proc is not None and proc.poll() is None

    def start(self):
        """Load the model in the background. Does nothing if it is loading or loaded; retries after a failure."""
        with self._lock:
            if self._closed or self.loading or self.ready:
                return
            self._stop_server()
            self._error = None
            self._finished.clear()
            self._thread = threading.Thread(target=self._load, name="minicpm-load", daemon=True)
            self._thread.start()

    def close(self):
        """Stop the server. The instance cannot be restarted afterwards."""
        with self._lock:
            self._closed = True
            self._stop_server()

    def ocr(self, image):
        """Return the text in a PIL image. Blocks until the model is loaded."""
        self._finished.wait()
        if self._error is not None:
            raise MiniCPMLoadError(f"MiniCPM-OCR failed to load: {self._error}")
        if not self.ready:
            raise RuntimeError("The MiniCPM-OCR server stopped unexpectedly. Capture again to restart it.")
        return self._request(image)

    def _request(self, image):
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="PNG", compress_level=1)
        data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        # Message layout and (effectively greedy) sampling follow the official MiniCPM-OCR SDK.
        payload = {
            "model": MODEL_ALIAS,
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": OCR_PROMPT},
            ]}],
            "max_tokens": 4096,
            "temperature": 0.01,
            "top_p": 0.001,
            "top_k": 1,
            "repeat_penalty": 1.0,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        request = urllib.request.Request(
            self._url + "/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with _local_opener.open(request, timeout=OCR_TIMEOUT) as response:
                result = json.load(response)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:500]
            raise RuntimeError(f"MiniCPM-OCR request failed (HTTP {e.code}): {detail}") from None

        text = result["choices"][0]["message"].get("content") or ""
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        return text.strip()

    # Loading -----------------------------------------------------------------

    def _load(self):
        try:
            server = self._find_llama_server()
            model = self._download(f"{MODEL_REPO_URL}/{MODEL_FILE}",
                                   os.path.join(self.model_dir, MODEL_FILE), "model")
            mmproj = self._download(f"{MODEL_REPO_URL}/{MMPROJ_FILE}",
                                    os.path.join(self.model_dir, MMPROJ_FILE), "vision model")
            self._status("Loading MiniCPM-OCR…")
            self._launch(server, model, mmproj)
            self._wait_until_healthy()
            # The first image after installing can take ~30 s while the GPU driver compiles
            # shaders; do it now rather than on the user's first capture.
            self._status("Warming up MiniCPM-OCR…")
            self._request(Image.new("RGB", (380, 75), "white"))
            self._status("MiniCPM-OCR ready")
        except Exception as e:
            self._error = e
            with self._lock:
                self._stop_server()
                closed = self._closed
            if not closed:
                self._status("MiniCPM-OCR failed", error=str(e))
        finally:
            self._finished.set()

    def _status(self, message, error=None):
        self._on_status(message, error)

    def _find_llama_server(self):
        if self.llama_server_path:
            if not os.path.isfile(self.llama_server_path):
                raise FileNotFoundError(
                    f"llama_server_path in settings.json does not exist: {self.llama_server_path}")
            return self.llama_server_path

        exe = "llama-server.exe" if os.name == "nt" else "llama-server"
        local = os.path.join(self.llama_dir, exe)
        if os.path.isfile(local):
            return local
        if os.name != "nt":
            found = shutil.which("llama-server")
            if found:
                return found
            raise FileNotFoundError(
                "llama-server was not found. Install llama.cpp or set llama_server_path in settings.json.")

        self._install_llama_cpp()
        return local

    def _install_llama_cpp(self):
        zip_path = self.llama_dir + ".zip"
        self._download(LLAMA_CPP_URL, zip_path, "llama.cpp")
        self._status("Unpacking llama.cpp…")
        staging = self.llama_dir + ".partial"
        shutil.rmtree(staging, ignore_errors=True)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(staging)
        # The archive may or may not wrap its files in a top-level folder.
        for folder, _subfolders, files in os.walk(staging):
            if "llama-server.exe" in files:
                break
        else:
            raise RuntimeError(f"llama-server.exe was not found in {LLAMA_CPP_ASSET}.")
        # self.llama_dir has no llama-server.exe at this point, so anything there is a leftover partial install.
        shutil.rmtree(self.llama_dir, ignore_errors=True)
        os.replace(folder, self.llama_dir)
        shutil.rmtree(staging, ignore_errors=True)
        os.remove(zip_path)

    def _download(self, url, dest, label):
        """Download url to dest unless it already exists, resuming a partial download."""
        if os.path.isfile(dest):
            return dest
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        part = dest + ".part"
        have = os.path.getsize(part) if os.path.isfile(part) else 0
        headers = {"User-Agent": USER_AGENT}
        if have:
            headers["Range"] = f"bytes={have}-"
        self._status(f"Downloading {label}…")
        try:
            response = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60)
        except urllib.error.HTTPError as e:
            if e.code == 416 and have:  # the partial file is already complete
                os.replace(part, dest)
                return dest
            raise RuntimeError(f"Downloading the {label} failed (HTTP {e.code}): {url}") from None
        except urllib.error.URLError as e:
            raise RuntimeError(f"Downloading the {label} failed: {e.reason}") from None

        with response:
            length = int(response.headers.get("Content-Length") or 0)
            if response.status == 206:
                mode, done = "ab", have
            else:
                mode, done = "wb", 0
            total = done + length if length else 0
            last_report = 0.0
            with open(part, mode) as f:
                while True:
                    chunk = response.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    now = time.monotonic()
                    if now - last_report >= 0.25:
                        last_report = now
                        if total:
                            self._status(f"Downloading {label}… {done * 100 // total}%")
                        else:
                            self._status(f"Downloading {label}… {done >> 20} MB")
        if total and done != total:
            raise RuntimeError(f"The {label} download was incomplete ({done} of {total} bytes). Try again to resume it.")
        os.replace(part, dest)
        return dest

    def _launch(self, server, model, mmproj):
        port = _free_port()
        command = [
            server,
            "--model", model,
            "--mmproj", mmproj,
            "--host", "127.0.0.1",
            "--port", str(port),
            "--alias", MODEL_ALIAS,
            "--ctx-size", "8192",
            "--parallel", "1",
            "--n-gpu-layers", "99",
            "--jinja",
            "--reasoning", "off",
        ]
        with self._lock:
            if self._closed:
                raise RuntimeError("The window was closed.")
            self._log = open(self.log_path, "wb")
            self._proc = subprocess.Popen(
                command,
                cwd=os.path.dirname(server),
                stdin=subprocess.DEVNULL,
                stdout=self._log,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            self._job = _kill_with_this_process(self._proc)
            self._url = f"http://127.0.0.1:{port}"

    def _wait_until_healthy(self):
        proc = self._proc
        deadline = time.monotonic() + SERVER_START_TIMEOUT
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f"llama-server exited with code {proc.returncode}.\n\n{self._log_tail()}")
            try:
                with _local_opener.open(self._url + "/health", timeout=2) as response:
                    if response.status == 200:
                        return
            except OSError:  # not listening yet, or HTTP 503 while the model loads
                pass
            time.sleep(0.25)
        raise TimeoutError(
            f"llama-server did not become ready within {SERVER_START_TIMEOUT} s.\n\n{self._log_tail()}")

    def _log_tail(self, limit=1200):
        try:
            with open(self.log_path, "rb") as f:
                f.seek(0, os.SEEK_END)
                f.seek(max(0, f.tell() - limit))
                tail = f.read().decode("utf-8", "replace").strip()
        except OSError:
            return ""
        return f"Last lines of {self.log_path}:\n{tail}"

    def _stop_server(self):
        """Terminate the server process. Call with self._lock held."""
        proc, self._proc = self._proc, None
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        if self._job is not None:
            _close_handle(self._job)
            self._job = None
        if self._log is not None:
            self._log.close()
            self._log = None


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _kill_with_this_process(proc):
    """On Windows, put proc in a job object that kills it when this process exits, even after a crash.

    Returns the job handle (close it to kill proc), or None if unavailable.
    """
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
    JobObjectExtendedLimitInformation = 9

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not (kernel32.SetInformationJobObject(job, JobObjectExtendedLimitInformation,
                                             ctypes.byref(info), ctypes.sizeof(info))
            and kernel32.AssignProcessToJobObject(job, int(proc._handle))):
        _close_handle(job)
        return None
    return job


def _close_handle(handle):
    import ctypes
    from ctypes import wintypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle(handle)
