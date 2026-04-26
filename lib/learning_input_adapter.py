class LearningInputAdapter:
    def __init__(self, midi_queues):
        self.midi_queues = midi_queues

    def drain_note_events(self, max_messages=None):
        events = self.midi_queues.drain_live_for_learning(max_messages=max_messages)
        return [
            (msg, timestamp)
            for msg, timestamp in events
            if getattr(msg, "type", None) in ("note_on", "note_off")
        ]
