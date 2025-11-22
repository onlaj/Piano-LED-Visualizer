"""
Central registry for LED animations.
Provides unified interface for managing and starting animations.
"""

from typing import Callable, Optional, Dict, Any, List
from lib.animation_speed import to_milliseconds, get_speed_manager, get_global_speed_ms


class AnimationInfo:
    """Metadata for an animation."""
    
    def __init__(self, 
                 name: str,
                 function: Callable,
                 display_name: str = None,
                 supports_speed: bool = False,
                 default_speed: Any = None,
                 requires_param: bool = False,
                 param_name: str = None,
                 web_id: str = None):
        """
        Initialize animation info.
        
        Args:
            name: Internal name (used in settings)
            function: Animation function to call
            display_name: Human-readable name (defaults to name)
            supports_speed: Whether animation supports speed configuration
            default_speed: Default speed value
            requires_param: Whether animation requires a parameter (like chords, colormap)
            param_name: Name of the parameter if required
            web_id: ID used in web interface (defaults to lowercase name)
        """
        self.name = name
        self.function = function
        self.display_name = display_name or name
        self.supports_speed = supports_speed
        self.default_speed = default_speed
        self.requires_param = requires_param
        self.param_name = param_name
        self.web_id = web_id or name.lower().replace(" ", "")
    
    def get_args(self, ledstrip, ledsettings, menu, param=None, usersettings=None):
        """
        Get arguments to pass to the animation function.
        Always uses global speed from settings.
        
        Args:
            ledstrip: LED strip instance
            ledsettings: LED settings instance
            menu: Menu instance
            param: Optional parameter value
            usersettings: Optional UserSettings for speed conversion
        
        Returns:
            tuple: Arguments for the animation function
        """
        # Handle parameter-based animations first
        if self.requires_param:
            if param is None:
                raise ValueError(f"Animation {self.name} requires parameter {self.param_name}")
            # Parameter goes before standard args for some animations
            if self.name in ("Chords", "colormap_animation"):
                args = [param, ledstrip, ledsettings, menu]
            else:
                args = [ledstrip, ledsettings, menu, param]
        else:
            args = [ledstrip, ledsettings, menu]
        
        # Only add speed_ms if animation supports speed
        if self.supports_speed:
            # Get global speed from settings
            if usersettings is None and hasattr(ledsettings, 'usersettings'):
                usersettings = ledsettings.usersettings
            
            # Get global speed in milliseconds
            speed_ms = get_global_speed_ms(usersettings)
            args.append(speed_ms)
        
        return tuple(args)


class AnimationRegistry:
    """Central registry for all LED animations."""
    
    def __init__(self):
        self._animations: Dict[str, AnimationInfo] = {}
        self._web_id_map: Dict[str, str] = {}  # web_id -> name
    
    def register(self, info: AnimationInfo):
        """
        Register an animation.
        
        Args:
            info: AnimationInfo instance
        """
        self._animations[info.name] = info
        self._web_id_map[info.web_id] = info.name
    
    def get(self, name: str) -> Optional[AnimationInfo]:
        """
        Get animation info by name.
        
        Args:
            name: Animation name or web_id
        
        Returns:
            AnimationInfo or None
        """
        # Try direct name lookup
        if name in self._animations:
            return self._animations[name]
        
        # Try web_id lookup
        if name in self._web_id_map:
            return self._animations[self._web_id_map[name]]
        
        return None
    
    def get_all(self) -> List[AnimationInfo]:
        """
        Get all registered animations.
        
        Returns:
            List of AnimationInfo
        """
        return list(self._animations.values())
    
    def get_by_web_id(self, web_id: str) -> Optional[AnimationInfo]:
        """
        Get animation by web interface ID.
        
        Args:
            web_id: Web interface ID
        
        Returns:
            AnimationInfo or None
        """
        if web_id in self._web_id_map:
            return self._animations[self._web_id_map[web_id]]
        return None
    
    def get_idle_animations(self) -> List[AnimationInfo]:
        """
        Get animations suitable for IDLE mode.
        Excludes animations that require parameters.
        
        Returns:
            List of AnimationInfo
        """
        return [info for info in self._animations.values() if not info.requires_param]
    
    def start_animation(self, 
                        name: str,
                        ledstrip,
                        ledsettings,
                        menu,
                        param=None,
                        usersettings=None,
                        is_idle=False):
        """
        Start an animation with global speed.
        
        Args:
            name: Animation name (internal name, not web_id)
            ledstrip: LED strip instance
            ledsettings: LED settings instance
            menu: Menu instance
            param: Optional parameter value (for Chords, Colormap)
            usersettings: Optional UserSettings for speed conversion
            is_idle: Whether this is an IDLE animation
        
        Returns:
            bool: True if animation was started, False if not found
        """
        # Get by name (internal name)
        info = self._animations.get(name)
        if info is None:
            return False
        
        # Get function arguments (always uses global speed)
        try:
            args = info.get_args(ledstrip, ledsettings, menu, param, usersettings)
        except ValueError as e:
            return False
        
        # Set running flag
        if is_idle:
            menu.is_idle_animation_running = True
        else:
            menu.is_animation_running = True
        
        # Start animation in thread
        import threading
        menu.t = threading.Thread(target=info.function, args=args)
        menu.t.start()
        
        return True


# Global registry instance
_registry = None


def get_registry() -> AnimationRegistry:
    """
    Get the global animation registry.
    
    Returns:
        AnimationRegistry: The global registry instance
    """
    global _registry
    if _registry is None:
        _registry = AnimationRegistry()
        _register_all_animations(_registry)
    return _registry


def _register_all_animations(registry: AnimationRegistry):
    """
    Register all animations in the registry.
    This function imports animation functions and registers them.
    """
    from lib.functions import (
        theaterChase, rainbow, rainbowCycle, theaterChaseRainbow,
        breathing, fireplace, sound_of_da_police, scanner,
        chords, colormap_animation
    )
    
    # Animations with speed support
    registry.register(AnimationInfo(
        name="Rainbow",
        function=rainbow,
        display_name="Rainbow",
        supports_speed=True,
        default_speed="Medium"
    ))
    
    registry.register(AnimationInfo(
        name="Rainbow Cycle",
        function=rainbowCycle,
        display_name="Rainbow Cycle",
        supports_speed=True,
        default_speed="Medium"
    ))
    
    registry.register(AnimationInfo(
        name="Breathing",
        function=breathing,
        display_name="Breathing",
        supports_speed=True,
        default_speed="Medium"
    ))
    
    registry.register(AnimationInfo(
        name="Theater Chase Rainbow",
        function=theaterChaseRainbow,
        display_name="Theater Chase Rainbow",
        supports_speed=True,
        default_speed="Medium"
    ))
    
    # Animations with fixed/default speed (now support speed but have defaults)
    registry.register(AnimationInfo(
        name="Theater Chase",
        function=theaterChase,
        display_name="Theater Chase",
        supports_speed=True,
        default_speed=20  # wait_ms in milliseconds
    ))
    
    registry.register(AnimationInfo(
        name="Fireplace",
        function=fireplace,
        display_name="Fireplace",
        supports_speed=True,
        default_speed=20  # wait_ms in milliseconds
    ))
    
    registry.register(AnimationInfo(
        name="Sound of da police",
        function=sound_of_da_police,
        display_name="Sound of da police",
        supports_speed=True,
        default_speed=5  # wait_ms in milliseconds
    ))
    
    registry.register(AnimationInfo(
        name="Scanner",
        function=scanner,
        display_name="Scanner",
        supports_speed=True,
        default_speed=1  # wait_ms in milliseconds
    ))
    
    # Animations with parameters
    registry.register(AnimationInfo(
        name="Chords",
        function=chords,
        display_name="Chords",
        supports_speed=False,
        requires_param=True,
        param_name="scale",
        web_id="chords"
    ))
    
    registry.register(AnimationInfo(
        name="colormap_animation",
        function=colormap_animation,
        display_name="Colormap",
        supports_speed=False,
        requires_param=True,
        param_name="colormap",
        web_id="colormap_animation"
    ))

