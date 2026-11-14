"""Configuración, rutas y constantes del servidor web."""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    cand = Path(sys._MEIPASS) / "postermaker"
    if cand.is_dir():
        BASE_DIR = cand
    else:
        BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

STATIC_DIR = BASE_DIR / "static"
OUTPUT_DIR = Path(
    os.environ.get(
        "POSTERMAKER_OUTPUT",
        str(Path(tempfile.gettempdir()) / "postermaker"),
    )
)
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
JOB_PATTERN = re.compile(r"^[0-9a-f]{32}$")
MAX_JOB_AGE_SECONDS = 6 * 60 * 60


def get_output_dir() -> Path:
    """Devuelve OUTPUT_DIR permitiendo que monkeypatch.setattr(web, 'OUTPUT_DIR', ...) funcione dinámicamente."""
    web_mod = sys.modules.get("postermaker.web")
    if web_mod and hasattr(web_mod, "OUTPUT_DIR"):
        return Path(getattr(web_mod, "OUTPUT_DIR"))
    return OUTPUT_DIR


def _parse_bool(val: str | None) -> bool | None:
    if val is None:
        return None
    val_clean = val.strip().lower()
    if val_clean in ("1", "true", "yes", "on", "t"):
        return True
    if val_clean in ("0", "false", "no", "off", "f"):
        return False
    return None


def is_local_mode() -> bool:
    """Determina si la aplicación se ejecuta en modo local (escritorio) o en la nube (cloud/Render).

    Por defecto es True (modo local).
    Precedencia:
    1. POSTERMAKER_LOCAL si está definido explícitamente ('1'/'true' -> True; '0'/'false' -> False).
    2. POSTERMAKER_CLOUD si está definido ('1'/'true' -> False; '0'/'false' -> True).
    3. POSTERMAKER_ENV: 'local', 'dev', 'development' -> True; 'cloud', 'production', 'staging' -> False.
    4. Detección automática de plataforma en la nube (RENDER='true', FLY_APP_NAME, K_SERVICE) -> False.
    5. Por defecto: True (modo local).
    """
    # 1. Variable explícita POSTERMAKER_LOCAL
    local_flag = _parse_bool(os.environ.get("POSTERMAKER_LOCAL"))
    if local_flag is not None:
        return local_flag

    # 2. Variable explícita POSTERMAKER_CLOUD
    cloud_flag = _parse_bool(os.environ.get("POSTERMAKER_CLOUD"))
    if cloud_flag is not None:
        return not cloud_flag

    # 3. Variable general POSTERMAKER_ENV
    env_str = os.environ.get("POSTERMAKER_ENV", "").strip().lower()
    if env_str in ("cloud", "production", "prod", "staging"):
        return False
    if env_str in ("local", "dev", "development"):
        return True

    # 4. Detección de plataformas en la nube
    if os.environ.get("RENDER"):
        return False
    if os.environ.get("FLY_APP_NAME") or os.environ.get("K_SERVICE"):
        return False

    # 5. Por defecto, modo local
    return True


def get_app_env() -> str:
    """Devuelve 'local' o 'cloud' según el modo detectado."""
    return "local" if is_local_mode() else "cloud"


def get_default_host() -> str:
    """Determina la dirección de enlace por defecto.

    Local: 127.0.0.1
    Cloud: 0.0.0.0 (para escuchar conexiones externas/del proxy de Render).
    Puede sobreescribirse mediante HOST o POSTERMAKER_HOST.
    """
    if "HOST" in os.environ and os.environ["HOST"].strip():
        return os.environ["HOST"].strip()
    if "POSTERMAKER_HOST" in os.environ and os.environ["POSTERMAKER_HOST"].strip():
        return os.environ["POSTERMAKER_HOST"].strip()
    return "127.0.0.1" if is_local_mode() else "0.0.0.0"


def get_default_port() -> int:
    """Determina el puerto por defecto.

    Render inyecta la variable $PORT. Si está presente, se respeta ese valor.
    En caso contrario, se usa 8000 por defecto.
    """
    port_str = os.environ.get("PORT") or os.environ.get("POSTERMAKER_PORT")
    if port_str:
        try:
            return int(port_str.strip())
        except ValueError:
            pass
    return 8000


def get_default_idle_timeout() -> int:
    """Determina el tiempo de espera por inactividad antes del apagado.

    Local: 900s (15 minutos).
    Cloud: 0 (desactivado, el servicio web debe permanecer activo indefinidamente).
    Puede sobreescribirse mediante IDLE_TIMEOUT o POSTERMAKER_IDLE_TIMEOUT.
    """
    timeout_str = os.environ.get("IDLE_TIMEOUT") or os.environ.get("POSTERMAKER_IDLE_TIMEOUT")
    if timeout_str:
        try:
            return max(0, int(timeout_str.strip()))
        except ValueError:
            pass
    return 900 if is_local_mode() else 0

