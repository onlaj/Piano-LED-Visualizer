"""
State Manager for Piano LED Visualizer

Manages three system states: Active Use, Normal, and IDLE
Each state has different CPU/power characteristics to optimize performance.
"""

import time
from enum import Enum
from lib.log_setup import logger


class SystemState(Enum):
    """System power states"""
    ACTIVE_USE = "active_use"  # MIDI messages being received
    NORMAL = "normal"          # Recent user activity (web/buttons)
    IDLE = "idle"              # No activity for extended period


class StateManager:
    """
    Manages system state transitions and timing parameters.
    
    States:
    - ACTIVE_USE: MIDI being played, no loop delay, screen 1Hz
    - NORMAL: Recent user activity, 0.006s loop delay, screen 10Hz  
    - IDLE: No activity, 0.9s loop delay, screen 1Hz
    """
    
    def __init__(self, usersettings):
        """
        Initialize state manager.
        
        Args:
            usersettings: UserSettings instance for reading configuration
        """
        self.usersettings = usersettings
        self.current_state = SystemState.NORMAL
        self.last_state = SystemState.NORMAL
        
        # Timing trackers
        self.last_midi_activity = 0.0
        self.last_user_activity = time.time()  # Start in normal mode
        self.last_state_change = time.time()
        
        # Screen refresh tracking
        self.last_screen_update = 0.0
        
        # Load configuration
        self.reload_config()
        
        logger.info(f"StateManager initialized in {self.current_state.value} mode")
    
    def reload_config(self):
        """Reload configuration from settings"""
        try:
            # IDLE delay in minutes (default 10 minutes)
            idle_timeout_value = self.usersettings.get_setting_value("idle_timeout_minutes")
            self.idle_timeout_minutes = float(idle_timeout_value) if idle_timeout_value else 10.0
            self.idle_timeout_seconds = self.idle_timeout_minutes * 60
            
            # MIDI to normal transition (1 minute after MIDI stops)
            self.midi_timeout_seconds = 60.0
            
            # Screen off delay (existing setting)
            screen_off_value = self.usersettings.get_setting_value("screen_off_delay")
            self.screen_off_delay = float(screen_off_value) * 60 if screen_off_value else 3600
            
            # Screensaver delay (existing setting)
            screensaver_value = self.usersettings.get_setting_value("screensaver_delay")
            self.screensaver_delay = float(screensaver_value) * 60 if screensaver_value else 600
            
            logger.debug(f"Config reloaded: idle_timeout={self.idle_timeout_minutes}min, "
                        f"screen_off={self.screen_off_delay/60}min, "
                        f"screensaver={self.screensaver_delay/60}min")
        except Exception as e:
            logger.warning(f"Error loading state manager config: {e}, using defaults")
            self.idle_timeout_seconds = 600  # 10 minutes
            self.midi_timeout_seconds = 60    # 1 minute
            self.screen_off_delay = 3600      # 60 minutes
            self.screensaver_delay = 600      # 10 minutes
    
    def update_midi_activity(self):
        """Called when MIDI message is received"""
        self.last_midi_activity = time.time()
        # MIDI activity also counts as general activity
        self.last_user_activity = time.time()
    
    def update_user_activity(self):
        """Called when user interacts (web, buttons)"""
        self.last_user_activity = time.time()
    
    def update_state(self, midiports=None, menu=None, current_time=None):
        """
        Update current system state based on activity timers.
        
        Args:
            midiports: MidiPorts instance (optional, for backward compatibility)
            menu: MenuLCD instance (optional, for backward compatibility)
            current_time: Current time as float (optional, defaults to time.time())
        
        Returns:
            SystemState: Current state after update
        """
        if current_time is None:
            current_time = time.time()
        
        # Sync with existing activity trackers if provided
        if midiports is not None:
            if midiports.last_activity > self.last_midi_activity:
                self.last_midi_activity = midiports.last_activity
        
        if menu is not None:
            if menu.last_activity > self.last_user_activity:
                self.last_user_activity = menu.last_activity
        
        # Calculate time since last activities
        time_since_midi = current_time - self.last_midi_activity
        time_since_user = current_time - self.last_user_activity
        
        # Determine new state
        new_state = self.current_state
        
        # State transition logic
        if time_since_midi < self.midi_timeout_seconds:
            # Recent MIDI activity → ACTIVE_USE
            new_state = SystemState.ACTIVE_USE
        elif time_since_user < self.idle_timeout_seconds:
            # Recent user activity but no MIDI → NORMAL
            new_state = SystemState.NORMAL
        else:
            # No activity for extended period → IDLE
            new_state = SystemState.IDLE
        
        # Handle state transitions
        if new_state != self.current_state:
            self._transition_state(new_state, current_time)
        
        self.current_state = new_state
        return new_state
    
    def _transition_state(self, new_state, current_time):
        """Handle state transition logic"""
        old_state = self.current_state
        logger.info(f"State transition: {old_state.value} → {new_state.value}")
        
        # Reset screen update timer on state change
        self.last_screen_update = 0.0
        self.last_state = old_state
        self.last_state_change = current_time
    
    def get_loop_delay(self):
        """
        Get appropriate main loop delay for current state.
        
        Returns:
            float: Sleep time in seconds
        """
        if self.current_state == SystemState.ACTIVE_USE:
            return 0.01  # 10ms delay - responsive but prevents CPU spinning
        elif self.current_state == SystemState.NORMAL:
            return 0.006  # Standard delay (~167Hz)
        else:  # IDLE
            return 0.9  # Large delay for CPU savings
    
    def should_refresh_screen(self):
        """
        Determine if screen should be refreshed based on current state.
        Uses internal timing to enforce refresh rates.
        
        Returns:
            bool: True if screen should refresh now
        """
        current_time = time.time()
        elapsed = current_time - self.last_screen_update
        
        if self.current_state == SystemState.ACTIVE_USE:
            # 1Hz during active use (save CPU during performance)
            if elapsed >= 1.0:
                self.last_screen_update = current_time
                return True
        elif self.current_state == SystemState.NORMAL:
            # 10Hz during normal use
            if elapsed >= 0.1:
                self.last_screen_update = current_time
                return True
        else:  # IDLE
            # 1Hz during idle
            if elapsed >= 1.0:
                self.last_screen_update = current_time
                return True
        
        return False
    
    def get_screen_refresh_interval(self):
        """
        Get screen refresh interval for current state.
        
        Returns:
            float: Interval in seconds
        """
        if self.current_state == SystemState.ACTIVE_USE:
            return 1.0  # 1Hz
        elif self.current_state == SystemState.NORMAL:
            return 0.1  # 10Hz
        else:  # IDLE
            return 1.0  # 1Hz
    
    def is_active_use(self):
        """Check if in ACTIVE_USE state"""
        return self.current_state == SystemState.ACTIVE_USE
    
    def is_normal(self):
        """Check if in NORMAL state"""
        return self.current_state == SystemState.NORMAL
    
    def is_idle(self):
        """Check if in IDLE state"""
        return self.current_state == SystemState.IDLE
    
    def should_run_screensaver(self, menu):
        """
        Determine if screensaver should run.
        
        Args:
            menu: MenuLCD instance
        
        Returns:
            bool: True if screensaver should start
        """
        # Don't run screensaver during active use
        if self.is_active_use():
            return False
        
        # Don't run if already running
        if getattr(menu, 'screensaver_is_running', False):
            return False
        
        # Check screensaver delay setting
        delay_minutes = int(getattr(menu, 'screensaver_delay', 0))
        if delay_minutes <= 0:
            return False
        
        # Check time since last activity
        current_time = time.time()
        time_since_activity = current_time - self.last_user_activity
        
        return time_since_activity > (delay_minutes * 60)
    
    def get_state_info(self):
        """
        Get current state information for debugging/display.
        
        Returns:
            dict: State information
        """
        current_time = time.time()
        return {
            'state': self.current_state.value,
            'time_since_midi': current_time - self.last_midi_activity,
            'time_since_user': current_time - self.last_user_activity,
            'loop_delay': self.get_loop_delay(),
            'screen_refresh_interval': self.get_screen_refresh_interval(),
        }

