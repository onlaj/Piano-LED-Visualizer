import threading
import time
from collections import deque


class MidiQueues:
    def __init__(
        self,
        *,
        live_maxlen=1000,
        file_maxlen=500,
        websocket_maxlen=1000,
        forward_maxlen=2048,
        scheduled_forward_maxlen=4096,
        websocket_publish_maxlen=512,
        reserved_noteoff_slots=None,
    ):
        self.live_visualizer_queue = deque(maxlen=live_maxlen)
        self.live_learning_queue = deque(maxlen=live_maxlen)
        self.file_queue = deque(maxlen=file_maxlen)
        self.websocket_queue = deque(maxlen=websocket_maxlen)
        self.live_forward_queue = deque(maxlen=forward_maxlen)
        self.scheduled_forward_queue = deque(maxlen=scheduled_forward_maxlen)
        self.websocket_publish_queue = deque(maxlen=websocket_publish_maxlen)
        self.reserved_noteoff_slots = (
            reserved_noteoff_slots
            if reserved_noteoff_slots is not None
            else max(1, min(32, live_maxlen // 8))
        )
        self.drop_counter = 0
        self.drop_counts = {}
        self._lock = threading.RLock()

    def classify_message(self, msg):
        msg_type = getattr(msg, "type", None)
        if msg_type == "note_off":
            return "note_off"
        if msg_type == "note_on":
            if getattr(msg, "velocity", 0) == 0:
                return "note_off"
            return "note_on"
        if msg_type == "control_change":
            return "control_change"
        return "other"

    def _increment_drop(self, key):
        self.drop_counter += 1
        self.drop_counts[key] = self.drop_counts.get(key, 0) + 1

    def _reserve_slots_for(self, queue):
        if not queue.maxlen:
            return self.reserved_noteoff_slots
        queue_reserve = max(1, queue.maxlen // 8)
        return min(self.reserved_noteoff_slots, queue_reserve)

    def queue_with_policy(self, queue, item, source, reserve_slots=0, count_drops=True):
        msg = item[0] if isinstance(item, tuple) else item
        event_type = self.classify_message(msg)
        soft_limit = queue.maxlen - reserve_slots if queue.maxlen else None

        if queue.maxlen:
            if event_type == "note_off":
                if len(queue) >= queue.maxlen:
                    if count_drops:
                        self._increment_drop(f"{source}_{event_type}")
                    return False
            elif soft_limit is not None and len(queue) >= max(0, soft_limit):
                key = f"{source}_{event_type if event_type == 'note_on' else 'noncritical'}"
                if count_drops:
                    self._increment_drop(key)
                return False

        queue.append(item)
        return True

    def enqueue_live(self, msg, timestamp=None):
        if timestamp is None:
            timestamp = time.perf_counter()
        item = (msg, timestamp)
        with self._lock:
            queued_visualizer = self.queue_with_policy(
                self.live_visualizer_queue,
                item,
                "live",
                reserve_slots=self.reserved_noteoff_slots,
            )
            queued_learning = self.queue_with_policy(
                self.live_learning_queue,
                item,
                "learning",
                reserve_slots=self.reserved_noteoff_slots,
                count_drops=False,
            )
            return queued_visualizer or queued_learning

    def enqueue_file(self, msg, timestamp=None):
        if timestamp is None:
            timestamp = time.perf_counter()
        with self._lock:
            self.file_queue.append((msg, timestamp))
            return True

    def enqueue_websocket(self, msg, timestamp=None):
        if timestamp is None:
            timestamp = time.perf_counter()
        with self._lock:
            return self.queue_with_policy(
                self.websocket_queue,
                (msg, timestamp),
                "websocket_input",
                reserve_slots=self._reserve_slots_for(self.websocket_queue),
            )

    def enqueue_live_forward(self, msg, timestamp=None, source="forward"):
        if timestamp is None:
            timestamp = time.perf_counter()
        with self._lock:
            return self.queue_with_policy(
                self.live_forward_queue,
                (msg, timestamp, source),
                source,
                reserve_slots=self._reserve_slots_for(self.live_forward_queue),
            )

    def peek_live_forward(self):
        with self._lock:
            if not self.live_forward_queue:
                return None
            return self.live_forward_queue[0]

    def pop_live_forward(self, expected=None):
        with self._lock:
            if not self.live_forward_queue:
                return None
            if expected is None:
                return self.live_forward_queue.popleft()
            for index, item in enumerate(self.live_forward_queue):
                if item == expected:
                    del self.live_forward_queue[index]
                    return item
            return None

    def enqueue_scheduled_forward(self, msg, enqueued_at=None, due_time=None, source="scheduled_forward"):
        if enqueued_at is None:
            enqueued_at = time.perf_counter()
        if due_time is None:
            due_time = enqueued_at
        item = (msg, enqueued_at, due_time, source)
        with self._lock:
            queued = self.queue_with_policy(
                self.scheduled_forward_queue,
                item,
                source,
                reserve_slots=self._reserve_slots_for(self.scheduled_forward_queue),
            )
            if queued:
                ordered = sorted(self.scheduled_forward_queue, key=lambda entry: entry[2])
                self.scheduled_forward_queue.clear()
                self.scheduled_forward_queue.extend(ordered)
            return queued

    def peek_due_scheduled_forward(self, now_perf=None):
        if now_perf is None:
            now_perf = time.perf_counter()
        with self._lock:
            if not self.scheduled_forward_queue:
                return None
            item = self.scheduled_forward_queue[0]
            if item[2] <= now_perf:
                return item
            return None

    def pop_due_scheduled_forward(self, now_perf=None, expected=None):
        if now_perf is None:
            now_perf = time.perf_counter()
        with self._lock:
            if not self.scheduled_forward_queue:
                return None
            if expected is None:
                item = self.scheduled_forward_queue[0]
                if item[2] <= now_perf:
                    return self.scheduled_forward_queue.popleft()
                return None
            for index, item in enumerate(self.scheduled_forward_queue):
                if item == expected:
                    del self.scheduled_forward_queue[index]
                    return item
            return None

    def peek_next_scheduled_forward(self):
        with self._lock:
            if not self.scheduled_forward_queue:
                return None
            return self.scheduled_forward_queue[0]

    def clear_scheduled_forward(self, source=None):
        with self._lock:
            if source is None:
                removed = len(self.scheduled_forward_queue)
                self.scheduled_forward_queue.clear()
                return removed
            kept = deque(
                item for item in self.scheduled_forward_queue if len(item) < 4 or item[3] != source
            )
            removed = len(self.scheduled_forward_queue) - len(kept)
            self.scheduled_forward_queue.clear()
            self.scheduled_forward_queue.extend(kept)
            return removed

    def enqueue_websocket_publish(self, msg, timestamp=None):
        if timestamp is None:
            timestamp = time.perf_counter()
        with self._lock:
            return self.queue_with_policy(
                self.websocket_publish_queue,
                (msg, timestamp),
                "websocket_publish",
                reserve_slots=0,
            )

    def pop_websocket_publish(self):
        with self._lock:
            if not self.websocket_publish_queue:
                return None
            return self.websocket_publish_queue.popleft()

    def drain_queue(self, queue, max_messages=None):
        drained = []
        with self._lock:
            while queue and (max_messages is None or len(drained) < max_messages):
                drained.append(queue.popleft())
        return drained

    def drain_live_for_visualizer(self, max_messages=None):
        return self.drain_queue(self.live_visualizer_queue, max_messages=max_messages)

    def drain_live_for_learning(self, max_messages=None):
        return self.drain_queue(self.live_learning_queue, max_messages=max_messages)

    def drain_file(self, max_messages=None):
        return self.drain_queue(self.file_queue, max_messages=max_messages)

    def drain_websocket(self, max_messages=None):
        return self.drain_queue(self.websocket_queue, max_messages=max_messages)

    def clear_file(self):
        with self._lock:
            self.file_queue.clear()

    def clear_websocket(self):
        with self._lock:
            self.websocket_queue.clear()

    def snapshot_depths(self):
        with self._lock:
            return {
                "live_input": len(self.live_visualizer_queue),
                "learning_input": len(self.live_learning_queue),
                "midi_file": len(self.file_queue),
                "websocket_input": len(self.websocket_queue),
                "live_forward": len(self.live_forward_queue),
                "scheduled_forward": len(self.scheduled_forward_queue),
                "websocket_publish": len(self.websocket_publish_queue),
            }
