import asyncio
import atexit
import threading

from waitress import serve

import webinterface as web_mod
from lib.log_setup import logger
from webinterface import webinterface, app_state


class WebInterfaceManager:
    def __init__(self, args, usersettings, ledsettings, ledstrip, learning, saving, midiports, menu, hotspot, platform):
        self.args = args
        self.usersettings = usersettings
        self.ledsettings = ledsettings
        self.ledstrip = ledstrip
        self.learning = learning
        self.saving = saving
        self.midiports = midiports
        self.menu = menu
        self.hotspot = hotspot
        self.platform = platform
        self.websocket_loop = asyncio.new_event_loop()
        self.setup_web_interface()

    def setup_web_interface(self):
        if self.args.webinterface != "false":
            logger.info('Starting webinterface')

            app_state.usersettings = self.usersettings
            app_state.ledsettings = self.ledsettings
            app_state.ledstrip = self.ledstrip
            app_state.learning = self.learning
            app_state.saving = self.saving
            app_state.midiports = self.midiports
            app_state.menu = self.menu
            app_state.hotspot = self.hotspot
            app_state.platform = self.platform

            webinterface.jinja_env.auto_reload = True
            webinterface.config['TEMPLATES_AUTO_RELOAD'] = True

            if not self.args.port:
                self.args.port = 80

            processThread = threading.Thread(
                target=serve,
                args=(webinterface,),
                kwargs={'host': '0.0.0.0', 'port': self.args.port, 'threads': 20},
                daemon=True
            )
            processThread.start()

            processThread = threading.Thread(
                target=web_mod.start_server,
                args=(self.websocket_loop,),
                daemon=True
            )
            processThread.start()

            atexit.register(web_mod.stop_server, self.websocket_loop)
