from __future__ import annotations

import json
from pathlib import Path
import pytest

from postermaker import service


def test_server_info_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "get_runtime_dir", lambda: tmp_path)

    # 1. Al inicio no debe existir
    assert service.read_server_info() is None

    # 2. Guardar información
    service.write_server_info("127.0.0.1", 8000, 12345)
    info = service.read_server_info()
    assert info is not None
    assert info["host"] == "127.0.0.1"
    assert info["port"] == 8000
    assert info["url"] == "http://127.0.0.1:8000"
    assert info["pid"] == 12345

    # 3. Eliminar información
    service.remove_server_info()
    assert service.read_server_info() is None


def test_launch_or_open_when_already_running(monkeypatch: pytest.MonkeyPatch) -> None:
    browser_opened = []
    monkeypatch.setattr(service, "_is_postermaker_running", lambda host, port: True)
    monkeypatch.setattr(service, "_open_in_browser", lambda url: browser_opened.append(url))

    code = service.launch_or_open()
    assert code == 0
    assert len(browser_opened) == 1
    assert "http://127.0.0.1" in browser_opened[0]


def test_launch_or_open_with_systemd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(service, "get_runtime_dir", lambda: tmp_path)
    browser_opened = []

    # Simular que al principio no corre, pero systemd lo arranca exitosamente
    state = {"running": False}

    def fake_is_running(host, port):
        return state["running"]

    def fake_start_systemd():
        state["running"] = True
        service.write_server_info("127.0.0.1", 8001, 9999)
        return True

    monkeypatch.setattr(service, "is_systemd_user_available", lambda: True)
    monkeypatch.setattr(service, "start_systemd_service", fake_start_systemd)
    monkeypatch.setattr(service, "_is_postermaker_running", fake_is_running)
    monkeypatch.setattr(service, "_open_in_browser", lambda url: browser_opened.append(url))

    code = service.launch_or_open()
    assert code == 0
    assert browser_opened == ["http://127.0.0.1:8001"]


def test_launch_or_open_fallback_direct_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service, "is_systemd_user_available", lambda: False)
    monkeypatch.setattr(service, "_is_postermaker_running", lambda host, port: False)
    monkeypatch.setattr(service, "read_server_info", lambda: None)

    runner_calls = []

    code = service.launch_or_open(web_runner=lambda args: runner_calls.append(args) or 0)
    assert code == 0
    assert len(runner_calls) == 1
    assert "--open" in runner_calls[0]
