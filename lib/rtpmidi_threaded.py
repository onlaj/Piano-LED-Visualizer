from lib.log_setup import logger
from pymidi import server
import threading


class MyHandler(server.Handler):
    def on_peer_connected(self, peer):
        print('Peer connected: {}'.format(peer))

    def on_peer_disconnected(self, peer):
        print('Peer disconnected: {}'.format(peer))

    def on_midi_commands(self, peer, command_list):
        for command in command_list:
            if command.command == 'note_on':
                key = command.params.key
                velocity = command.params.velocity
                print('Someone hit the key {} with velocity {}'.format(key, velocity))


class ThreadedMIDIServer:
    def __init__(self, host='0.0.0.0', port=5004):
        self.host = host
        self.port = port
        self.server = None
        self.thread = None
        self.running = False

    def start(self):
        """Start the MIDI server in a separate thread."""
        if self.running:

            logger.warning("Server is already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_server)
        self.thread.daemon = True  # Thread will close when main program exits
        self.thread.start()
        logger.info(f"MIDI server started on {self.host}:{self.port}")

    def stop(self):
        """Stop the MIDI server."""
        if not self.running:
            return

        self.running = False
        if self.server:
            self.server.close()
        if self.thread:
            self.thread.join()
        logger.info("MIDI server stopped")

    def _run_server(self):
        """Internal method to run the server."""
        try:
            bind_addr = f"{self.host}:{self.port}"
            self.server = server.Server.from_bind_addrs([bind_addr])
            self.server.add_handler(MyHandler())
            self.server.serve_forever()
        except Exception as e:
            logger.info(f"Server error: {e}")
            self.running = False
