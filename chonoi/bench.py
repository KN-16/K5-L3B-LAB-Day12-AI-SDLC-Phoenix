"""Đo Canvas của cảnh Gather bằng Chromium và đồng hồ khung hình thực."""

import argparse
import json
import math
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from .contract import load_contract
from .errors import BadInput
from .live import LiveGame, LiveServer, WEB_DIR, _Handler

WIDTH, HEIGHT = 1280, 720
WARMUP_MS = 3000


def summarize(intervals, load_ms):
    frames = len(intervals)
    measured = sum(intervals) / 1000
    slow_count = max(1, math.ceil(frames * 0.01))
    slow_ms = sum(sorted(intervals, reverse=True)[:slow_count]) / slow_count
    return {"avg_fps": frames / measured, "p1_low_fps": 1000 / slow_ms,
            "frames": frames, "measured_s": measured, "load_ms": max(0, round(load_ms))}


def _chromium():
    requested = os.environ.get("CHONOI_BROWSER")
    if requested:
        return shutil.which(requested) or requested
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "msedge"):
        executable = shutil.which(name)
        if executable:
            return executable
    candidates = [
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
    ]
    for key in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        root = os.environ.get(key)
        if root:
            candidates.extend(Path(root) / app for app in (
                "Google/Chrome/Application/chrome.exe", "Microsoft/Edge/Application/msedge.exe",
            ))
    for path in candidates:
        if path.is_file():
            return str(path)
    raise OSError("Cần Chrome, Chromium hoặc Edge. Có thể khai đường dẫn bằng CHONOI_BROWSER.")


def _handler(config, finished, sample):
    source = (Path(WEB_DIR) / "index.html").read_text(encoding="utf-8")
    config_script = "<script>window.chonoiBench = " + json.dumps(config) + ";</script>"
    page = source.replace("<script>", config_script + "\n<script>", 1).encode("utf-8")

    class Handler(_Handler):
        def handle(self):
            try:
                super().handle()
            except (BrokenPipeError, ConnectionResetError):
                # Chromium can close a polling connection when the benchmark ends.
                pass

        def do_GET(self):
            if self.path == "/":
                self._send(200, page, "text/html; charset=utf-8")
            else:
                super().do_GET()

        def do_POST(self):
            if self.path != "/bench-result":
                super().do_POST()
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 4_000_000:
                    raise ValueError
                data = json.loads(self.rfile.read(size))
                intervals = data["intervals"]
                load = data["load_ms"]
                if (not isinstance(intervals, list) or not intervals
                        or any(type(n) not in (int, float) or not math.isfinite(n) or n <= 0 for n in intervals)
                        or type(load) not in (int, float) or not math.isfinite(load)
                        or (data["width"], data["height"]) != (WIDTH, HEIGHT)):
                    raise ValueError
            except (KeyError, TypeError, ValueError):
                self._send(400, b"{}")
                return
            sample.update(summarize(intervals, load))
            self._send(200, b"{}")
            finished.set()

    return Handler


def run_bench(tuning, seed, duration, started_ms):
    executable = _chromium()
    finished, sample = threading.Event(), {}
    config = {"width": WIDTH, "height": HEIGHT, "duration_ms": duration * 1000,
              "warmup_ms": WARMUP_MS, "started_ms": started_ms}
    handler = _handler(config, finished, sample)
    server = LiveServer(LiveGame("gather", tuning, {}, seed), port=0, handler_class=handler)
    scratch = Path("tmp")
    scratch.mkdir(exist_ok=True)
    server.start()
    try:
        with tempfile.TemporaryDirectory(prefix="bench-", dir=scratch.resolve(), ignore_cleanup_errors=True) as profile:
            browser = subprocess.Popen([
                executable, "--headless", "--no-first-run", "--disable-background-networking",
                "--hide-scrollbars", "--force-device-scale-factor=1",
                f"--window-size={WIDTH},{HEIGHT}", f"--user-data-dir={profile}", server.url,
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                deadline = time.monotonic() + duration + 30
                while not finished.wait(0.15):
                    if browser.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError("trình duyệt chưa trả mẫu đo Canvas")
            finally:
                if browser.poll() is None:
                    browser.terminate()
                    try:
                        browser.wait(timeout=4)
                    except subprocess.TimeoutExpired:
                        browser.kill()
                        browser.wait()
    finally:
        server.stop()
    return sample


def main(argv=None):
    started_ms = time.time_ns() / 1_000_000
    parser = argparse.ArgumentParser(description="Đo cảnh Gather 1280×720 bằng Chromium.")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if not math.isfinite(args.duration) or args.duration <= 0:
        parser.error("--duration phải là số giây dương hữu hạn")
    try:
        result = run_bench(load_contract()["tuning"], args.seed, args.duration, started_ms)
        args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    except (BadInput, OSError, RuntimeError) as error:
        parser.exit(1, f"benchmark: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
