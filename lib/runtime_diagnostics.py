import os
import threading


class RuntimeDiagnostics:
    def __init__(self, enabled=None):
        if enabled is None:
            enabled = os.environ.get("PLV_RUNTIME_DIAGNOSTICS", "1") != "0"
        self.enabled = enabled
        self._lock = threading.Lock()
        self._timings = {}
        self._queues = {}
        self._counters = {}
        self._gauges = {}
        self._metadata = {}

    def record_duration(self, name, seconds):
        if not self.enabled:
            return
        elapsed_ms = max(0.0, float(seconds) * 1000.0)
        with self._lock:
            metric = self._timings.setdefault(
                name,
                {"count": 0, "total_ms": 0.0, "max_ms": 0.0, "last_ms": 0.0},
            )
            metric["count"] += 1
            metric["total_ms"] += elapsed_ms
            metric["last_ms"] = elapsed_ms
            if elapsed_ms > metric["max_ms"]:
                metric["max_ms"] = elapsed_ms

    def observe_queue(self, name, depth, oldest_age_ms=0.0):
        if not self.enabled:
            return
        current_depth = max(0, int(depth))
        current_age_ms = max(0.0, float(oldest_age_ms or 0.0))
        with self._lock:
            metric = self._queues.setdefault(
                name,
                {
                    "current_depth": 0,
                    "max_depth": 0,
                    "current_oldest_age_ms": 0.0,
                    "max_oldest_age_ms": 0.0,
                },
            )
            metric["current_depth"] = current_depth
            metric["current_oldest_age_ms"] = current_age_ms
            if current_depth > metric["max_depth"]:
                metric["max_depth"] = current_depth
            if current_age_ms > metric["max_oldest_age_ms"]:
                metric["max_oldest_age_ms"] = current_age_ms

    def increment_counter(self, name, amount=1):
        if not self.enabled:
            return
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + amount

    def set_gauge(self, name, value):
        if not self.enabled:
            return
        with self._lock:
            self._gauges[name] = value

    def set_metadata(self, name, value):
        if not self.enabled:
            return
        with self._lock:
            self._metadata[name] = value

    def snapshot(self):
        with self._lock:
            timings = {
                name: {
                    "count": metric["count"],
                    "avg_ms": round(metric["total_ms"] / metric["count"], 4) if metric["count"] else 0.0,
                    "max_ms": round(metric["max_ms"], 4),
                    "last_ms": round(metric["last_ms"], 4),
                    "total_ms": round(metric["total_ms"], 4),
                }
                for name, metric in self._timings.items()
            }
            queues = {
                name: {
                    "current_depth": metric["current_depth"],
                    "max_depth": metric["max_depth"],
                    "current_oldest_age_ms": round(metric["current_oldest_age_ms"], 4),
                    "max_oldest_age_ms": round(metric["max_oldest_age_ms"], 4),
                }
                for name, metric in self._queues.items()
            }
            return {
                "enabled": self.enabled,
                "timings": timings,
                "queues": queues,
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "metadata": dict(self._metadata),
            }

    def reset(self):
        with self._lock:
            self._timings = {}
            self._queues = {}
            self._counters = {}
            self._gauges = {}
            self._metadata = {}
