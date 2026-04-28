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
