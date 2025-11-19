from flask import Flask
import asyncio
import websockets
from lib.functions import get_ip_address
import json
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


# Create a single instance of AppState
app_state = AppState()


def start_server(loop):
    async def learning(websocket):
        try:
            while True:
                await asyncio.sleep(0.01)
                for msg in app_state.learning.socket_send[:]:
                    await websocket.send(str(msg))
                    app_state.learning.socket_send.remove(msg)
        except:
            # Handle the connection closed error
            pass

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