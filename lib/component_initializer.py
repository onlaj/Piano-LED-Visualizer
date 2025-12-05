import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from lib import colormaps as cmap
from lib.functions import startup_animation, fastColorWipe
from lib.learnmidi import LearnMIDI
from lib.ledsettings import LedSettings
from lib.ledstrip import LedStrip
from lib.log_setup import logger
from lib.menulcd import MenuLCD
from lib.midiports import MidiPorts
from lib.platform import PlatformRasp, PlatformNull, Hotspot
from lib.savemidi import SaveMIDI
from lib.usersettings import UserSettings


class ComponentInitializer:
    def __init__(self, args):
        self.args = args
        
        # Phase 1: Initialize independent components in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            platform_future = executor.submit(
                lambda: PlatformRasp() if self.args.appmode == "platform" else PlatformNull()
            )
            usersettings_future = executor.submit(UserSettings)
            saving_future = executor.submit(SaveMIDI)
            
            # Wait for all phase 1 components
            self.platform = platform_future.result()
            self.usersettings = usersettings_future.result()
            self.saving = saving_future.result()
        
        # Phase 2: Initialize components that depend on UserSettings in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            midiports_future = executor.submit(MidiPorts, self.usersettings)
            ledsettings_future = executor.submit(LedSettings, self.usersettings)
            
            # Wait for phase 2 components
            self.midiports = midiports_future.result()
            self.ledsettings = ledsettings_future.result()
        
        # Phase 3: Initialize LedStrip (depends on LedSettings)
        self.ledstrip = LedStrip(self.usersettings, self.ledsettings, self.args.leddriver)
        
        # Phase 4: Initialize Hotspot (depends on Platform)
        self.hotspot = Hotspot(self.platform)
        
        # Phase 5: Initialize LearnMIDI (depends on multiple components)
        self.learning = LearnMIDI(self.usersettings, self.ledsettings, self.midiports, self.ledstrip)
        
        # Phase 6: Initialize MenuLCD (depends on everything)
        self.menu = MenuLCD("config/menu.xml", self.args, self.usersettings, self.ledsettings,
                            self.ledstrip, self.learning, self.saving, self.midiports,
                            self.hotspot, self.platform)
        self.setup_components()

    def setup_components(self):
        logger.info(self.args)
        
        # Move platform operations to background threads (non-blocking)
        def disable_midi_scripts():
            if not self.args.skipupdate:
                try:
                    self.platform.disable_system_midi_scripts()
                except Exception as e:
                    logger.warning(f"Error disabling system MIDI scripts: {e}")
        
        def install_midi2abc():
            try:
                self.platform.install_midi2abc()
            except Exception as e:
                logger.warning(f"Error installing midi2abc: {e}")
        
        # Start platform operations in background
        threading.Thread(target=disable_midi_scripts, daemon=True).start()
        threading.Thread(target=install_midi2abc, daemon=True).start()

        cmap.gradients.update(cmap.load_colormaps())
        
        # Determine which colormap(s) are needed based on current color mode
        colormaps_to_generate = []
        if self.ledsettings.color_mode == "Rainbow":
            colormap_name = self.ledsettings.rainbow_colormap
            if colormap_name and colormap_name in cmap.gradients:
                colormaps_to_generate.append(colormap_name)
        elif self.ledsettings.color_mode == "VelocityRainbow":
            colormap_name = self.ledsettings.velocityrainbow_colormap
            if colormap_name and colormap_name in cmap.gradients:
                colormaps_to_generate.append(colormap_name)
        
        # Generate only the currently selected colormap(s) at startup
        # Others will be generated lazily on first access
        if colormaps_to_generate:
            cmap.generate_colormaps(cmap.gradients, self.ledstrip.led_gamma, colormaps_to_generate)
        else:
            # If no specific colormap needed, still initialize with current gamma
            # Pass None to trigger legacy behavior that generates all colormaps
            cmap.generate_colormaps(cmap.gradients, self.ledstrip.led_gamma, None)
        
        cmap.update_multicolor(self.ledsettings.multicolor_range, self.ledsettings.multicolor)

        t = threading.Thread(target=startup_animation, args=(self.ledstrip, self.ledsettings))
        t.start()

        self.midiports.add_instance(self.menu)
        self.ledsettings.add_instance(self.menu, self.ledstrip)
        self.saving.add_instance(self.menu)
        self.learning.add_instance(self.menu)

        self.menu.show()
        self.midiports.last_activity = time.time()
        self.hotspot.hotspot_script_time = time.time()

        # Start MIDI device monitoring for auto-connection
        self.midiports.start_midi_monitor()

        fastColorWipe(self.ledstrip.strip, True, self.ledsettings)
