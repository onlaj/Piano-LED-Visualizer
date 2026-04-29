#!/usr/bin/env python3

import sys

sys.path.append("./")
sys.path.append("../")

from webinterface import app_state, webinterface
import webinterface.views_api as views_api


class _DummyMenu:
    def __init__(self):
        self.last_activity = 0
        self.is_idle_animation_running = False


def _client_with_songs_dir(monkeypatch, tmp_path):
    songs_dir = tmp_path / "Songs"
    songs_dir.mkdir()
    monkeypatch.setattr(views_api, "SONGS_DIR", songs_dir.resolve())
    monkeypatch.setattr(app_state, "menu", _DummyMenu())
    monkeypatch.setattr(app_state, "state_manager", None)
    return webinterface.test_client(), songs_dir


def test_change_song_name_without_cache_does_not_fail(monkeypatch, tmp_path):
    client, songs_dir = _client_with_songs_dir(monkeypatch, tmp_path)
    (songs_dir / "No cache.mid").write_text("", encoding="utf-8")

    response = client.get(
        "/api/change_setting",
        query_string={
            "setting_name": "change_song_name",
            "value": "No cache.mid",
            "second_value": "Renamed.mid",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    assert not (songs_dir / "No cache.mid").exists()
    assert (songs_dir / "Renamed.mid").exists()


def test_download_missing_song_returns_clean_404(monkeypatch, tmp_path):
    client, _songs_dir = _client_with_songs_dir(monkeypatch, tmp_path)

    response = client.get(
        "/api/change_setting",
        query_string={"setting_name": "download_song", "value": "Missing.mid"},
    )

    assert response.status_code == 404
    payload = response.get_json()
    assert payload["success"] is False
    assert "not found" in payload["error"]


def test_song_api_rejects_path_traversal(monkeypatch, tmp_path):
    client, _songs_dir = _client_with_songs_dir(monkeypatch, tmp_path)

    response = client.get(
        "/api/change_setting",
        query_string={"setting_name": "start_midi_play", "value": "../secret.mid"},
    )

    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_remove_bundle_only_touches_expected_prefix(monkeypatch, tmp_path):
    client, songs_dir = _client_with_songs_dir(monkeypatch, tmp_path)
    for name in ("Suite_main.mid", "Suite_left.mid", "OtherSuite_main.mid", "Suiteevil.mid"):
        (songs_dir / name).write_text("", encoding="utf-8")

    response = client.get(
        "/api/change_setting",
        query_string={"setting_name": "remove_song", "value": "Suite_main.mid"},
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    assert not (songs_dir / "Suite_main.mid").exists()
    assert not (songs_dir / "Suite_left.mid").exists()
    assert (songs_dir / "OtherSuite_main.mid").exists()
    assert (songs_dir / "Suiteevil.mid").exists()
