"""Reinicio no bloqueante del servicio del sistema."""

from __future__ import annotations

import shutil
import subprocess
import threading
import time


def schedule_service_restart() -> None:
    """Reinicia el servicio systemd de usuario en segundo plano tras una breve pausa."""
    def _restart_worker():
        time.sleep(1.2)
        if shutil.which("systemctl"):
            try:
                subprocess.run(
                    ["systemctl", "--user", "restart", "postermaker.service"],
                    capture_output=True,
                    check=False,
                )
            except Exception:
                pass

    threading.Thread(target=_restart_worker, daemon=True).start()
