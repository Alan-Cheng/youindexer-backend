import importlib

import app.config as config_module


def test_storage_state_paths_default_to_none(monkeypatch) -> None:
    monkeypatch.delenv("INSTAGRAM_STORAGE_STATE_PATH", raising=False)
    monkeypatch.delenv("THREADS_STORAGE_STATE_PATH", raising=False)

    reloaded = importlib.reload(config_module)

    assert reloaded.settings.instagram_storage_state_path is None
    assert reloaded.settings.threads_storage_state_path is None


def test_storage_state_paths_read_from_env(monkeypatch) -> None:
    monkeypatch.setenv("INSTAGRAM_STORAGE_STATE_PATH", "/secrets/ig_state.json")
    monkeypatch.setenv("THREADS_STORAGE_STATE_PATH", "/secrets/threads_state.json")

    reloaded = importlib.reload(config_module)

    assert reloaded.settings.instagram_storage_state_path == "/secrets/ig_state.json"
    assert reloaded.settings.threads_storage_state_path == "/secrets/threads_state.json"

    # Restore the module-level singleton other tests import for their app instance.
    monkeypatch.delenv("INSTAGRAM_STORAGE_STATE_PATH", raising=False)
    monkeypatch.delenv("THREADS_STORAGE_STATE_PATH", raising=False)
    importlib.reload(config_module)
