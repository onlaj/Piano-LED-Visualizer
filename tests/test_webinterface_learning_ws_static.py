#!/usr/bin/env python3

from pathlib import Path


def test_learning_websocket_cancels_peer_task_when_one_side_closes():
    source = Path("webinterface/__init__.py").read_text(encoding="utf-8")

    assert "asyncio.wait" in source
    assert "FIRST_COMPLETED" in source
    assert ".cancel()" in source


def test_learning_and_broadcast_use_client_snapshots_before_sending():
    source = Path("webinterface/__init__.py").read_text(encoding="utf-8")

    assert "list(app_state.websocket_midi_clients)" in source
    assert ".discard(websocket)" in source


def test_ports_page_midi_logging_checkbox_syncs_on_and_off():
    source = Path("webinterface/static/js/ui.js").read_text(encoding="utf-8")

    assert 'checkbox.checked = String(response["midi_logging"]) === "1"' in source


def test_main_websocket_uses_stable_midi_event_handler_across_ajax_pages():
    source = Path("webinterface/templates/index.html").read_text(encoding="utf-8")

    assert "window.handleMidiEvent = function(rawData)" in source
    assert "window.mainWebSocketMessageHandlers" in source
    assert "for (const handler of window.mainWebSocketMessageHandlers)" in source


def test_song_stop_button_stops_browser_player_and_backend_playback():
    # The onclick reference lives in songs.html; the function body is in index.js
    songs_source = Path("webinterface/templates/songs.html").read_text(encoding="utf-8")
    assert "stop_midi_playback()" in songs_source

    index_source = Path("webinterface/static/index.js").read_text(encoding="utf-8")
    assert "document.getElementById('midi_player').stop()" in index_source
    assert "change_setting('stop_midi_play'" in index_source


def test_recording_status_syncs_play_and_stop_buttons_both_directions():
    source = Path("webinterface/static/js/ui.js").read_text(encoding="utf-8")

    assert "start_midi_play" in source
    assert "stop_midi_play" in source
    assert "classList.remove(\"hidden\")" in source
    assert "classList.add(\"hidden\")" in source
    assert "Object.keys(response[\"isplaying\"]).length === 0" in source
    # Sync function handles playback state restoration
    assert "sync_playback_state" in source


def test_song_backend_play_uses_explicit_song_name_attribute():
    source = Path("webinterface/templates/songs.html").read_text(encoding="utf-8")

    assert "data-song-name" in source
    assert "start_midi_playback()" in source
    assert "midi_player').src" not in source


def test_song_playback_helpers_are_loaded_globally_not_only_in_ajax_html():
    source = Path("webinterface/static/index.js").read_text(encoding="utf-8")

    assert "function start_midi_playback()" in source
    assert "function stop_midi_playback()" in source
    assert "dataset.songName" in source
    assert "change_setting('start_midi_play', songName)" in source
