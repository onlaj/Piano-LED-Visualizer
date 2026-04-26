#!/usr/bin/env python3

from pathlib import Path


def test_practice_template_registers_cleanup_for_reloaded_ajax_page():
    template = Path("webinterface/templates/practice.html").read_text(encoding="utf-8")

    assert "window.__pianoLedPracticeCleanup" in template
    assert "function addPracticeListener" in template
    assert "target.removeEventListener(eventName, handler, options)" in template
    assert "addPracticeListener(window, 'message'" in template
    assert "addPracticeListener(window, 'resize'" in template
    assert "addPracticeListener(window, 'orientationchange'" in template
    assert "addPracticeListener(window, 'beforeunload'" in template
