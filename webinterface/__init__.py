from flask import Flask
import asyncio
import websockets
import threading
from lib.functions import get_ip_address
import time

UPLOAD_FOLDER = 'Songs/'


webinterface = Flask(__name__, template_folder='templates')
webinterface.config['TEMPLATES_AUTO_RELOAD'] = True
webinterface.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
webinterface.config['MAX_CONTENT_LENGTH'] = 32 * 1000 * 1000

webinterface.socket_input = []

print("Socket listening on: " + str(get_ip_address())+":8765")

def start_server():
    async def echo(websocket):
        while True:
            time.sleep(0.01)
            for msg in webinterface.socket_input[:]:
                print("input msg: " + str(msg))
                await websocket.send(str(msg))
                webinterface.socket_input.remove(msg)
            message = websocket.recv()


    async def main():
        async with websockets.serve(echo, get_ip_address(), 8765):
            await asyncio.Future()

    asyncio.run(main())


processThread = threading.Thread(target=start_server, daemon=True)
processThread.start()


from webinterface import views
from webinterface import views_api