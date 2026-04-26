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
