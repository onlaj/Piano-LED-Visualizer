#!/usr/bin/env python3

import sys

sys.path.append("./")
sys.path.append("../")

import lib.colormaps as cmap


def test_update_multicolor_does_not_change_lazy_default_gamma(monkeypatch):
    monkeypatch.setattr(cmap, "_current_gamma", 2.4)
    cmap.colormaps.clear()
    cmap.colormaps_preview.clear()

    cmap.update_multicolor([[20, 30], [31, 40]], [[255, 0, 0], [0, 255, 0]])

    assert cmap._current_gamma == 2.4
    assert "^Multicolor" in dict.keys(cmap.colormaps)
