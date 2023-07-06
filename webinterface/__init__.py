from flask import Flask
import asyncio
import websockets
import threading
from lib.functions import get_ip_address
import time
import atexit

UPLOAD_FOLDER = 'Songs/'

webinterface = Flask(__name__, template_folder='templates')
webinterface.config['TEMPLATES_AUTO_RELOAD'] = True
webinterface.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
webinterface.config['MAX_CONTENT_LENGTH'] = 32 * 1000 * 1000

webinterface.socket_input = []

print("Socket listening on: " + str(get_ip_address())+":8765")


def start_server():
    async def echo(websocket):
        try:
            while True:
                time.sleep(0.01)
                for msg in webinterface.learning.socket_send[:]:
                    await websocket.send(str(msg))
                    webinterface.learning.socket_send.remove(msg)
        except:
            # Handle the connection closed error
            # You can log the error or perform any necessary cleanup tasks
            pass

    async def main():
        async with websockets.serve(echo, get_ip_address(), 8765):
            await asyncio.Future()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())


# Stop the WebSocket server and cancel pending tasks on shutdown
def stop_server():
    loop = asyncio.get_event_loop()
    for task in asyncio.all_tasks(loop=loop):
        task.cancel()
    loop.stop()


processThread = threading.Thread(target=start_server, daemon=True)
processThread.start()

# Register the shutdown handler
atexit.register(stop_server)

from webinterface import views
from webinterface import views_api