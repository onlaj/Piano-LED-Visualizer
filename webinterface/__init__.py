from flask import Flask
import asyncio
import websockets
from lib.functions import get_ip_address
import json
from collections import deque
from lib.log_setup import logger

UPLOAD_FOLDER = 'Songs/'

webinterface = Flask(__name__,
                     static_folder='static',
                     template_folder='templates')
webinterface.config['TEMPLATES_AUTO_RELOAD'] = True
webinterface.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
webinterface.config['MAX_CONTENT_LENGTH'] = 32 * 1000 * 1000
webinterface.json.sort_keys = False

webinterface.socket_input = []
webinterface.websocket_midi_send = deque(maxlen=100)  # Thread-safe queue for MIDI messages to send to websocket clients
webinterface.websocket_midi_send_lock = None  # Lock for synchronizing async consumers (initialized in start_server)


# State container to hold app components
class AppState:
    def __init__(self):
        self.usersettings = None
        self.ledsettings = None
        self.ledstrip = None
        self.learning = None
        self.saving = None
        self.midiports = None
        self.menu = None
        self.hotspot = None
        self.platform = None
        self.state_manager = None
        self.ledemu_clients = set()  # Track active LED emulator clients
        self.ledemu_pause = False
        self.current_profile_id = None
        # Currently selected profile id (set by web UI); None if not selected
        self.practice_active = False  # Track when practice tab is active
        self.websocket_midi_clients = set()  # Track active websocket MIDI clients


# Create a single instance of AppState
app_state = AppState()


def start_server(loop):
    async def broadcast_midi_to_clients():
        """Background task to broadcast MIDI messages to all connected clients."""
        logger.info("Starting MIDI broadcast task")
        while True:
            try:
                if app_state.practice_active:
                    messages = []
                    # Safely move messages from queue to local list
                    # deque append is atomic, but we use a robust pattern: 
                    # popleft until empty
                    while True:
                        try:
                            messages.append(webinterface.websocket_midi_send.popleft())
                        except IndexError:
                            break
                    
                    if messages:
                        if not app_state.websocket_midi_clients:
                            continue
                            
                        # Create send tasks for all clients
                        send_tasks = []
                        disconnected_clients = set()
                        
                        for ws in app_state.websocket_midi_clients:
                            for msg in messages:
                                try:
                                    # Create a task for each send so one slow client doesn't block others
                                    send_tasks.append(asyncio.create_task(ws.send(str(msg))))
                                except Exception:
                                    disconnected_clients.add(ws)
                        
                        if send_tasks:
                            await asyncio.gather(*send_tasks, return_exceptions=True)
                            
                        # Cleanup disconnected clients
                        if disconnected_clients:
                            app_state.websocket_midi_clients -= disconnected_clients
                            
                await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"Error in MIDI broadcast task: {e}")
                await asyncio.sleep(1)

    async def learning(websocket):
        try:
            app_state.websocket_midi_clients.add(websocket)
            logger.info(f"WebSocket MIDI client connected. Active clients: {len(app_state.websocket_midi_clients)}")
            
            async def send_messages():
                """Send outgoing messages to client."""
                try:
                    while True:
                        await asyncio.sleep(0.01)
                        # Send learning messages
                        for msg in app_state.learning.socket_send[:]:
                            await websocket.send(str(msg))
                            app_state.learning.socket_send.remove(msg)
                except websockets.exceptions.ConnectionClosed:
                    pass
                except Exception as e:
                    logger.warning(f"Error sending websocket message: {e}")
            
            async def receive_messages():
                """Receive incoming MIDI messages from client."""
                try:
                    async for message in websocket:
                        try:
                            # Check if it's a MIDI message string
                            if isinstance(message, str) and message.startswith("midi_event"):
                                # Forward to midiports for processing
                                if app_state.midiports:
                                    app_state.midiports.add_websocket_midi_message(message)
                            # Could also handle JSON format: {"type": "midi_message", "data": "..."}
                            elif isinstance(message, str):
                                try:
                                    data = json.loads(message)
                                    if data.get("type") == "midi_message" and "data" in data:
                                        if app_state.midiports:
                                            app_state.midiports.add_websocket_midi_message(data["data"])
                                except (json.JSONDecodeError, KeyError):
                                    # Not a JSON MIDI message, ignore
                                    pass
                        except Exception as e:
                            logger.warning(f"Error processing websocket MIDI message: {e}")
                except websockets.exceptions.ConnectionClosed:
                    pass
                except Exception as e:
                    logger.warning(f"Error receiving websocket message: {e}")
            
            # Run both send and receive concurrently
            await asyncio.gather(send_messages(), receive_messages())
        except Exception as e:
            logger.warning(f"WebSocket learning handler error: {e}")
        finally:
            if websocket in app_state.websocket_midi_clients:
                app_state.websocket_midi_clients.remove(websocket)
                logger.info(f"WebSocket MIDI client disconnected. Active clients: {len(app_state.websocket_midi_clients)}")

    async def ledemu_recv(websocket):
        async for message in websocket:
            try:
                msg = json.loads(message)
                if msg["cmd"] == "pause":
                    app_state.ledemu_pause = True
                elif msg["cmd"] == "resume":
                    app_state.ledemu_pause = False
            except websockets.exceptions.ConnectionClosed:
                pass
            except websockets.exceptions.WebSocketException:
                pass
            except Exception as e:
                logger.warning(e)
                return

    async def ledemu(websocket):
        try:
            app_state.ledemu_clients.add(websocket)
            logger.info(f"LED emulator client connected. Active clients: {len(app_state.ledemu_clients)}")

            await websocket.send(json.dumps({"settings":
                                                 {"gamma": app_state.ledstrip.led_gamma,
                                                  "reverse": app_state.ledstrip.reverse}}))

            previous_leds = None
            while not websocket.closed and websocket in app_state.ledemu_clients:  # Check both conditions
                try:
                    ledstrip = app_state.ledstrip
                    await asyncio.sleep(1 / ledstrip.WEBEMU_FPS)

                    if app_state.ledemu_pause:
                        continue

                    # Check connection is still open before sending
                    if websocket.closed:
                        break

                    current_leds = ledstrip.strip.getPixels()
                    if previous_leds != current_leds:  # Only send if LED state has changed
                        try:
                            await websocket.send(json.dumps({"leds": current_leds}))
                            previous_leds = list(current_leds)  # Create a copy of the list
                        except websockets.exceptions.ConnectionClosed:
                            break

                except websockets.exceptions.ConnectionClosed:
                    break
                except websockets.exceptions.WebSocketException:
                    break
                except Exception as e:
                    logger.warning(f"LED emulator error: {str(e)}")
                    break
        finally:
            if websocket in app_state.ledemu_clients:
                app_state.ledemu_clients.remove(websocket)
                logger.info(f"LED emulator client disconnected. Active clients: {len(app_state.ledemu_clients)}")
            try:
                await websocket.close()
            except:
                pass

    async def handler(websocket):
        try:
            # Support both newer (websocket.request.path) and older (websocket.path) versions
            try:
                path = websocket.request.path
            except AttributeError:
                path = websocket.path
            
            if path == "/learning":
                await learning(websocket)
            elif path == "/ledemu":
                await asyncio.gather(ledemu(websocket), ledemu_recv(websocket))
            else:
                # No handler for this path; close the connection.
                return
        except Exception as e:
            logger.warning(f"WebSocket handler error: {str(e)}")
        finally:
            if websocket in app_state.ledemu_clients:
                app_state.ledemu_clients.remove(websocket)
                logger.info(
                    f"LED emulator client disconnected (handler cleanup). Active clients: {len(app_state.ledemu_clients)}")

    async def main():
        # Initialize the global broadcast task
        asyncio.create_task(broadcast_midi_to_clients())
        
        listen_ip = app_state.usersettings.get_setting_value("web_listen_ip")

        if listen_ip and listen_ip != "0.0.0.0":
            show_ip = listen_ip
        else:
            show_ip = str(get_ip_address())
            listen_ip = "0.0.0.0"

        logger.info("WebSocket listening on: " + show_ip + ":8765")
        async with websockets.serve(handler, listen_ip, 8765):
            await asyncio.Future()

    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())


# Stop the WebSocket server and cancel pending tasks on shutdown
def stop_server(loop):
    for task in asyncio.all_tasks(loop=loop):
        task.cancel()
    loop.stop()


# Import views after app is defined to avoid circular imports
from webinterface import views, views_api
from webinterface import webinterface, app_state

# Attach profile manager without modifying existing AppState.__init__
try:
    from lib.profile_manager import ProfileManager
    if not hasattr(app_state, 'profile_manager'):
        app_state.profile_manager = ProfileManager()
except Exception as e:
    # Silent-ish failure keeps app running
    logger.warning(f"ProfileManager init failed: {e}")