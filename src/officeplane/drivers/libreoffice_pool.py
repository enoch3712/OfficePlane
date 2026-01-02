import os
import shutil
import socket
import subprocess
import threading
import time
import queue
import logging
from dataclasses import dataclass
from typing import Optional, Dict

from officeplane.observability.metrics import INSTANCE_RESTARTS, POOL_READY

log = logging.getLogger("officeplane.pool")

def find_soffice_binary() -> str:
    for cmd in ["soffice", "libreoffice"]:
        path = shutil.which(cmd)
        if path:
            return path
    return "/usr/bin/soffice"

@dataclass
class InstanceStatus:
    port: int
    ready: bool
    restarts: int
    last_error: Optional[str]

class LibreOfficeInstance:
    def __init__(self, port: int):
        self.port = port
        self.uno_port = port + 100
        self.process: Optional[subprocess.Popen] = None
        self.lock = threading.Lock()
        self.started = False
        self.restarts = 0
        self.last_error: Optional[str] = None
        self.soffice_path = find_soffice_binary()
        # isolate profile by HOME per instance
        self.home_dir = f"/tmp/officeplane_lo_home_{port}"
        os.makedirs(self.home_dir, exist_ok=True)

    def is_running(self) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.3)
                return s.connect_ex(("127.0.0.1", self.port)) == 0
        except Exception:
            return False

    def start(self) -> None:
        with self.lock:
            if self.is_running():
                self.started = True
                return

            log.info("starting libreoffice instance", extra={"port": self.port})
            env = os.environ.copy()
            env["HOME"] = self.home_dir  # helps isolate LO state

            cmd = [
                "unoserver",
                "--port", str(self.port),
                "--uno-port", str(self.uno_port),
                "--executable", self.soffice_path,
            ]

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            )

            for _ in range(30):
                if self.is_running():
                    self.started = True
                    self.last_error = None
                    log.info("instance ready", extra={"port": self.port})
                    return
                time.sleep(0.3)

            self.started = False
            self.last_error = "failed to start"
            log.error("instance failed to start", extra={"port": self.port})

    def stop(self) -> None:
        with self.lock:
            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=5)
                except Exception:
                    try:
                        self.process.kill()
                    except Exception:
                        pass
                self.process = None
            self.started = False

    def restart_async(self, reason: str) -> None:
        def _do():
            self.restarts += 1
            INSTANCE_RESTARTS.labels(port=str(self.port)).inc()
            self.last_error = reason
            log.warning("restarting instance", extra={"port": self.port, "stage": reason})
            self.stop()
            self.start()
        threading.Thread(target=_do, daemon=True).start()

    def convert_pipe(self, input_bytes: bytes, timeout_sec: int) -> bytes:
        if not self.started:
            self.start()

        cmd = ["unoconvert", "--port", str(self.port), "--convert-to", "pdf", "-", "-"]
        t0 = time.time()
        try:
            proc = subprocess.run(
                cmd,
                input=input_bytes,
                capture_output=True,
                timeout=timeout_sec,
            )
            if proc.returncode == 0 and proc.stdout:
                log.info("conversion ok", extra={"port": self.port, "duration_ms": int((time.time()-t0)*1000)})
                return proc.stdout

            err = proc.stderr.decode(errors="ignore") if proc.stderr else "unknown error"
            self.restart_async(f"unoconvert_failed:{proc.returncode}")
            raise RuntimeError(f"unoconvert failed ({proc.returncode}): {err}")

        except subprocess.TimeoutExpired:
            self.restart_async("timeout")
            raise RuntimeError("unoconvert timed out")


class LibreOfficePool:
    def __init__(self, size: int, start_port: int, convert_timeout_sec: int):
        self.size = size
        self.start_port = start_port
        self.convert_timeout_sec = convert_timeout_sec
        self.instances = [LibreOfficeInstance(start_port + i) for i in range(size)]
        self.q: "queue.Queue[LibreOfficeInstance]" = queue.Queue()
        self._ready_lock = threading.Lock()
        self._ready = 0

    def start_all_async(self) -> None:
        def _warm():
            for inst in self.instances:
                inst.start()
                with self._ready_lock:
                    if inst.started:
                        self._ready += 1
                        POOL_READY.set(self._ready)
                self.q.put(inst)
                time.sleep(0.2)
        threading.Thread(target=_warm, daemon=True).start()

    def status(self) -> Dict:
        return {
            "total": self.size,
            "ready": self._ready,
            "instances": [
                {
                    "port": inst.port,
                    "ready": inst.started,
                    "restarts": inst.restarts,
                    "last_error": inst.last_error,
                }
                for inst in self.instances
            ]
        }

    def convert(self, input_bytes: bytes) -> bytes:
        inst = self.q.get()
        try:
            return inst.convert_pipe(input_bytes, timeout_sec=self.convert_timeout_sec)
        finally:
            self.q.put(inst)
