#!/usr/bin/env python3

import sys
import unittest

sys.path.append("./")
sys.path.append("../")

from lib.runtime_diagnostics import RuntimeDiagnostics


class TestRuntimeDiagnostics(unittest.TestCase):
    def test_record_duration_aggregates_count_average_and_max(self):
        diagnostics = RuntimeDiagnostics()

        diagnostics.record_duration("main_loop", 0.002)
        diagnostics.record_duration("main_loop", 0.006)

        snapshot = diagnostics.snapshot()
        main_loop = snapshot["timings"]["main_loop"]

        self.assertEqual(main_loop["count"], 2)
        self.assertEqual(main_loop["avg_ms"], 4.0)
        self.assertEqual(main_loop["max_ms"], 6.0)

    def test_observe_queue_tracks_current_and_peak_depth_and_age(self):
        diagnostics = RuntimeDiagnostics()

        diagnostics.observe_queue("live_input", depth=3, oldest_age_ms=12.5)
        diagnostics.observe_queue("live_input", depth=1, oldest_age_ms=4.0)

        snapshot = diagnostics.snapshot()
        live_input = snapshot["queues"]["live_input"]

        self.assertEqual(live_input["current_depth"], 1)
        self.assertEqual(live_input["max_depth"], 3)
        self.assertEqual(live_input["current_oldest_age_ms"], 4.0)
        self.assertEqual(live_input["max_oldest_age_ms"], 12.5)

    def test_reset_clears_previous_samples(self):
        diagnostics = RuntimeDiagnostics()
        diagnostics.record_duration("main_loop", 0.005)
        diagnostics.observe_queue("live_input", depth=2, oldest_age_ms=9.0)
        diagnostics.increment_counter("strip_show_calls", 3)
        diagnostics.set_gauge("requested_loop_sleep_ms", 2.0)
        diagnostics.set_metadata("system_state", "active_use")

        diagnostics.reset()

        snapshot = diagnostics.snapshot()
        self.assertEqual(snapshot["timings"], {})
        self.assertEqual(snapshot["queues"], {})
        self.assertEqual(snapshot["counters"], {})
        self.assertEqual(snapshot["gauges"], {})
        self.assertEqual(snapshot["metadata"], {})


if __name__ == "__main__":
    unittest.main()
