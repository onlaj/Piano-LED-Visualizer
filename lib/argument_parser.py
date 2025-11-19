import argparse

from lib.rpi_drivers import RPiException
from lib.usersettings import UserSettings


class ArgumentParser:
    def __init__(self):
        self.args = self.parse_arguments()

    def parse_arguments(self):
        appmode_default = 'platform'
        if isinstance(RPiException, RuntimeError):
            appmode_default = 'app'

        parser = argparse.ArgumentParser()
        parser.add_argument('-c', '--clear', action='store_true', help='clear the display on exit')
        parser.add_argument('-d', '--display', type=str, help="choose type of display: '1in44' (default) | '1in3'")
        parser.add_argument('-f', '--fontdir', type=str, help="Use an alternate directory for fonts")
        parser.add_argument('-p', '--port', type=int, help="set port for webinterface (80 is default)")
        parser.add_argument('-s', '--skipupdate', action='store_true',
                            help="Do not try to update /usr/local/bin/connectall.py")
        parser.add_argument('-w', '--webinterface', help="disable webinterface: 'true' (default) | 'false'")
        parser.add_argument('-r', '--rotatescreen', default="false", help="rotate screen: 'false' (default) | 'true'")
        parser.add_argument('-a', '--appmode', default=appmode_default, help="appmode: 'platform' (default) | 'app'")
        parser.add_argument('-l', '--leddriver', default="rpi_ws281x",
                            help="leddriver: 'rpi_ws281x' (default) | 'emu' ")
        args = parser.parse_args()
        
        # Load display_type from settings if not provided via CLI
        if args.display is None:
            usersettings = UserSettings()
            display_type = usersettings.get_setting_value("display_type")
            if display_type:
                args.display = display_type
        
        return args
