"""Gestión de inactividad, control de pestañas y liberación de recursos."""

from __future__ import annotations

import os
import shutil
import threading
import time

from .config import get_output_dir


class InactivityManager:
    """Gestiona el apagado automático por inactividad y la liberación de memoria/recursos."""

    def __init__(self, timeout_seconds: int = 900, tab_close_grace_seconds: int = 180):
        self.timeout = timeout_seconds
        self.tab_close_grace = tab_close_grace_seconds
        self.last_activity = time.time()
        self.active_tabs = 1
        self._lock = threading.Lock()
        self._stopped = False
        self._thread: threading.Thread | None = None

    def touch(self) -> None:
        with self._lock:
            self.last_activity = time.time()

    def heartbeat(self) -> None:
        with self._lock:
            self.last_activity = time.time()
            if self.active_tabs <= 0:
                self.active_tabs = 1

    def tab_opened(self) -> None:
        with self._lock:
            self.active_tabs += 1
            self.last_activity = time.time()

    def tab_closed(self) -> None:
        with self._lock:
            if self.active_tabs > 0:
                self.active_tabs -= 1
            self.last_activity = time.time()

    def shutdown(self, reason: str = "Inactividad") -> None:
        print(f"Liberando recursos del sistema ({reason})...")
        try:
            output_dir = get_output_dir()
            if output_dir.is_dir():
                shutil.rmtree(output_dir, ignore_errors=True)
        except Exception:
            pass
        import gc
        gc.collect()
        os._exit(0)

    def start(self) -> None:
        if self.timeout <= 0:
            return

        def _monitor() -> None:
            while not self._stopped:
                time.sleep(10)
                with self._lock:
                    elapsed = time.time() - self.last_activity
                    tabs = self.active_tabs

                if tabs == 0 and elapsed >= self.tab_close_grace:
                    self.shutdown(reason=f"Sin pestañas activas tras {int(elapsed)}s")
                    break

                if elapsed >= self.timeout:
                    self.shutdown(reason=f"Inactividad total tras {int(elapsed)}s")
                    break

        self._thread = threading.Thread(target=_monitor, daemon=True)
        self._thread.start()


inactivity_manager = InactivityManager()
