"""
Unified speed system for LED animations.
Supports both preset speeds (Slow/Medium/Fast) and custom numeric values.
"""


class AnimationSpeed:
    """Manages animation speed conversion and configuration."""
    
    # Default preset values in milliseconds
    DEFAULT_SLOW = 50
    DEFAULT_MEDIUM = 20
    DEFAULT_FAST = 5
    
    def __init__(self, usersettings=None):
        """
        Initialize speed system with optional user settings.
        
        Args:
            usersettings: UserSettings instance to load speed presets from
        """
        if usersettings:
            self.slow_ms = int(usersettings.get_setting_value("animation_speed_slow") or self.DEFAULT_SLOW)
            self.medium_ms = int(usersettings.get_setting_value("animation_speed_medium") or self.DEFAULT_MEDIUM)
            self.fast_ms = int(usersettings.get_setting_value("animation_speed_fast") or self.DEFAULT_FAST)
        else:
            self.slow_ms = self.DEFAULT_SLOW
            self.medium_ms = self.DEFAULT_MEDIUM
            self.fast_ms = self.DEFAULT_FAST
    
    def to_milliseconds(self, speed):
        """
        Convert speed value to milliseconds.
        
        Args:
            speed: Can be:
                - String preset: "Slow", "Medium", "Fast"
                - Integer/float: Custom milliseconds value
                - None: Returns default medium speed
        
        Returns:
            int: Speed in milliseconds
        """
        if speed is None:
            return self.medium_ms
        
        # Handle string presets (case-insensitive)
        if isinstance(speed, str):
            speed_lower = speed.lower().strip()
            if speed_lower == "slow":
                return self.slow_ms
            elif speed_lower == "medium":
                return self.medium_ms
            elif speed_lower == "fast":
                return self.fast_ms
            else:
                # Try to parse as number
                try:
                    return int(float(speed))
                except (ValueError, TypeError):
                    return self.medium_ms
        
        # Handle numeric values
        try:
            return int(float(speed))
        except (ValueError, TypeError):
            return self.medium_ms
    
    def get_preset_name(self, speed_ms):
        """
        Get the closest preset name for a given milliseconds value.
        
        Args:
            speed_ms: Speed in milliseconds
        
        Returns:
            str: "Slow", "Medium", or "Fast"
        """
        try:
            speed_ms = float(speed_ms)
            # Find closest preset
            slow_diff = abs(speed_ms - self.slow_ms)
            medium_diff = abs(speed_ms - self.medium_ms)
            fast_diff = abs(speed_ms - self.fast_ms)
            
            if slow_diff <= medium_diff and slow_diff <= fast_diff:
                return "Slow"
            elif medium_diff <= fast_diff:
                return "Medium"
            else:
                return "Fast"
        except (ValueError, TypeError):
            return "Medium"
    
    def is_custom_speed(self, speed):
        """
        Check if a speed value is a custom numeric value (not a preset).
        
        Args:
            speed: Speed value to check
        
        Returns:
            bool: True if custom numeric value, False if preset
        """
        if speed is None:
            return False
        
        if isinstance(speed, str):
            speed_lower = speed.lower().strip()
            if speed_lower in ("slow", "medium", "fast"):
                return False
            # Try to parse as number
            try:
                float(speed)
                return True
            except (ValueError, TypeError):
                return False
        
        # Numeric value - check if it matches a preset
        try:
            speed_ms = float(speed)
            return (speed_ms != self.slow_ms and 
                   speed_ms != self.medium_ms and 
                   speed_ms != self.fast_ms)
        except (ValueError, TypeError):
            return False


# Global instance (will be initialized with usersettings when available)
_speed_manager = None


def get_speed_manager(usersettings=None):
    """
    Get or create the global speed manager instance.
    
    Args:
        usersettings: Optional UserSettings instance to initialize with
    
    Returns:
        AnimationSpeed: The global speed manager
    """
    global _speed_manager
    if _speed_manager is None or usersettings is not None:
        _speed_manager = AnimationSpeed(usersettings)
    return _speed_manager


def to_milliseconds(speed, usersettings=None):
    """
    Convenience function to convert speed to milliseconds.
    
    Args:
        speed: Speed value (preset string or numeric)
        usersettings: Optional UserSettings instance
    
    Returns:
        int: Speed in milliseconds
    """
    manager = get_speed_manager(usersettings)
    return manager.to_milliseconds(speed)


def get_global_speed_ms(usersettings):
    """
    Get the global animation speed in milliseconds from settings.
    
    Args:
        usersettings: UserSettings instance
    
    Returns:
        int: Global speed in milliseconds
    """
    if usersettings is None:
        return AnimationSpeed.DEFAULT_MEDIUM
    
    # Get global speed setting
    speed_setting = usersettings.get_setting_value("led_animation_speed")
    
    if not speed_setting or speed_setting.strip() == "":
        # No global speed set, use default medium
        return AnimationSpeed.DEFAULT_MEDIUM
    
    # Convert to milliseconds using speed manager
    manager = get_speed_manager(usersettings)
    return manager.to_milliseconds(speed_setting)

