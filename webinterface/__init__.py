from flask import Flask
import asyncio
import websockets
from lib.functions import get_ip_address
import json
from lib.log_setup import logger


UPLOAD_FOLDER = 'Songs/'

webinterface = Flask(__name__, template_folder='templates')
webinterface.config['TEMPLATES_AUTO_RELOAD'] = True
webinterface.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
webinterface.config['MAX_CONTENT_LENGTH'] = 32 * 1000 * 1000
webinterface.json.sort_keys = False

webinterface.socket_input = []

def start_server(loop):
    async def learning(websocket):
        try:
            while True:
                await asyncio.sleep(0.01)
                for msg in webinterface.learning.socket_send[:]:
                    await websocket.send(str(msg))
                    webinterface.learning.socket_send.remove(msg)
        except:
            # Handle the connection closed error
            # You can log the error or perform any necessary cleanup tasks
            pass

    async def ledemu_recv(websocket):
        async for message in websocket:
            try:
                msg = json.loads(message)
                if msg["cmd"] == "pause":
                    webinterface.ledemu_pause = True
                elif msg["cmd"] == "resume":
                    webinterface.ledemu_pause = False
            except websockets.exceptions.ConnectionClosed:
                pass
            except websockets.exceptions.WebSocketException:
                pass
            except Exception as e:
                logger.warning(e)
                return

    async def ledemu(websocket):
        try:
            await websocket.send(json.dumps({"settings": 
                {"gamma": webinterface.ledstrip.led_gamma,
                 "reverse": webinterface.ledstrip.reverse}}))
        except:
            pass

        while True:
            try:
                ledstrip = webinterface.ledstrip
                await asyncio.sleep(1 / ledstrip.WEBEMU_FPS)

                if webinterface.ledemu_pause:
                    continue

                await websocket.send(json.dumps({"leds": ledstrip.strip.getPixels()}))

            except websockets.exceptions.ConnectionClosed:
                pass
            except websockets.exceptions.WebSocketException:
                pass
            except:
                logger.warning(e)
                return

    async def handler(websocket):
        if websocket.path == "/learning":
            await learning(websocket)
        elif websocket.path == "/ledemu":
            await asyncio.gather(ledemu(websocket), ledemu_recv(websocket))
        else:
            # No handler for this path; close the connection.
            return

    async def main():
        logger.info("WebSocket listening on: " + str(get_ip_address())+":8765")
        async with websockets.serve(handler, "0.0.0.0", 8765):
            await asyncio.Future()

    webinterface.ledemu_pause = False

    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())


# Stop the WebSocket server and cancel pending tasks on shutdown
def stop_server(loop):
    for task in asyncio.all_tasks(loop=loop):
        task.cancel()
    loop.stop()


from webinterface import views
from webinterface import views_api