import numpy as np
import os
import glob
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from lib.log_setup import logger

# Global state for lazy loading
_current_gamma = 1.0
_colormaps_lock = Lock()

# Lazy-loading wrapper for colormaps dict
class _LazyColormapDict(dict):
    """Dict-like wrapper that generates colormaps on-demand."""
    def __getitem__(self, key):
        ensure_colormap_generated(key)
        # Use dict.__getitem__ to bypass our __getitem__ and avoid recursion
        return dict.__getitem__(self, key)
    
    def __contains__(self, key):
        # Check if gradient exists, not if colormap is generated
        return key in gradients
    
    def get(self, key, default=None):
        if key in self:
            return self[key]
        return default
    
    def keys(self):
        # Return all available gradient names
        return gradients.keys()
    
    def __iter__(self):
        return iter(gradients.keys())

colormaps = _LazyColormapDict()
colormaps_preview = {}

# Colormap gradients designed with ws281x gamma = 1
# These will be converted to colormap lookup tables with 256 entries for use in colormaps dict
gradients = {}

# Hard-coded gradients:

# Rainbow, as existing in lib/functions.py, equiv to FastLED-HSV Spectrum
gradients["Rainbow"] = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 0, 0)]

# FastLED Rainbow - https://github.com/FastLED/FastLED/wiki/FastLED-HSV-Colors
gradients["Rainbow-FastLED"] = [(0.0, (255, 0, 0)), (0.125, (170, 85, 0)), (0.25, (170, 170, 0)), (0.375, (0, 255, 0)),
                                (0.5, (0, 170, 85)), (0.625, (0, 0, 255)), (1.0, (255, 0, 0))]
# Rainbow-FastLED-Y2: Should the 0.375 green have some red?
# gradients["Rainbow-FastLED-Y2"] = [ (0.0, (255,0,0)), (0.125, (170,85,0)), (0.25, (255,255,0)), (0.375, (0,255,0)), (0.5, (0,170,85)), (0.625, (0,0,255)), (1.0, (255,0,0)) ]

gradients["Pastel"] = [(255, 72, 72), (72, 255, 72), (72, 72, 255), (255, 72, 72)]

gradients["Ice-Cyclic"] = [(0.0, (0, 128, 128)), (0.25, (0, 0, 255)), (0.5, (128, 0, 128)), (0.75, (86, 86, 86)),
                           (1.0, (0, 128, 128))]
gradients["Cool-Cyclic"] = [(0.0, (0, 128, 0)), (0.25, (0, 126, 128)), (0.5, (0, 0, 255)), (0.75, (86, 86, 86)),
                            (1.0, (0, 128, 0))]
gradients["Warm-Cyclic"] = [(0.0, (255, 0, 0)), (0.4, (170, 64, 0)), (0.6, (128, 126, 0)), (0.8, (86, 85, 86)),
                            (1.0, (255, 0, 0))]


# Gradients from files:
#
# matplotlib: https://matplotlib.org/stable/gallery/color/colormap_reference.html
# cmasher: https://cmasher.readthedocs.io/user/introduction.html
# colorcet: https://colorcet.com
# cmocean: https://matplotlib.org/cmocean/
# hsluv and hpluv: https://www.hsluv.org/
#
# agama: https://github.com/GalacticDynamics-Oxford/Agama/
#     Agama/doc/Colormaps.pdf
#     Agama/py/agamacolormaps.py
# "circle" is a constant-brightness, perceptually uniform cyclic rainbow map
# going from magenta through blue, green and red back to magenta.
#
# "mist" is another replacement for "jet" or "rainbow" maps, which differs from "breeze" by
# having smaller dynamical range in brightness. The red and blue endpoints are darker than
# the green center, but not as dark as in "breeze", while the center is not as bright.
#
# "earth" is a rainbow-like colormap with increasing luminosity, going from black through
# dark blue, medium green in the middle and light red/orange to white.
# It is nearly perceptually uniform, monotonic in luminosity, and is suitable for
# plotting nearly anything, especially velocity maps (blue/redshifted).
# It resembles "gist_earth" (but with more vivid colors) or MATLAB's "parula".


# Homemade rough equivalent to matplotlib's LinearSegmentedColormap.from_list()

def gradient_to_cmaplut(gradient, gamma=1, entries=256, int_table=True):
    """Linear-interpolate gradient to a colormap lookup."""
    _CYCLIC_UNDUP = False

    # expected gradient format option 1: (position, (red, green, blue))
    if len(gradient[0]) == 2:
        pos, colors = zip(*gradient)
        r, g, b = zip(*colors)
    # expected gradient format option 2: (red, green, blue)
    elif len(gradient[0]) == 3:
        pos = np.linspace(0, 1, num=len(gradient))
        r, g, b = zip(*gradient)
    # expected gradient format option 3: [pos, red, green, blue], for future np.loadtxt from file
    elif len(gradient[0]) == 4:
        pos, r, g, b = zip(*gradient)
    else:
        raise Exception("Unknown input format")

    # if colors are int, then assumed 0-255 range, float 0-1 range
    if isinstance(r[0], float):
        div255 = False
    elif isinstance(r[0], int):
        div255 = True

    # if colormap is cyclic (first color matches last color), then do not include endpoint during calculation 
    # to prevent index 0 and 255 being duplicate color
    if _CYCLIC_UNDUP and (r[0], g[0], b[0]) == (r[-1], g[-1], b[-1]):
        xpoints = np.linspace(0, 1, num=entries, endpoint=False)
    else:
        xpoints = np.linspace(0, 1, num=entries, endpoint=True)

    # output tables
    table = np.zeros((3, entries), dtype=float)

    for i, c in enumerate((r, g, b)):
        c01 = np.divide(c, 255) if div255 else c
        table[i] = np.interp(xpoints, pos, c01) ** (1 / gamma)

    if int_table:
        return [(round(x[0] * 255), round(x[1] * 255), round(x[2] * 255)) for x in table.T]
    else:
        return [(x[0], x[1], x[2]) for x in table.T]


def update_colormap(name, gamma):
    """Generate a colormap from its gradient. Thread-safe."""
    global colormaps, colormaps_preview, gradients, _current_gamma

    try:
        if name not in gradients:
            logger.warning(f"Gradient {name} not found")
            return
        
        with _colormaps_lock:
            # Store directly in the underlying dict
            dict.__setitem__(colormaps, name, gradient_to_cmaplut(gradients[name], gamma))
            colormaps_preview[name] = gradient_to_cmaplut(gradients[name], 2.2, 64)
            _current_gamma = gamma
    except Exception as e:
        logger.warning(f"Loading colormap {name} failed: {e}")


def ensure_colormap_generated(name, gamma=None):
    """Ensure a colormap is generated, generating it lazily if needed. Thread-safe."""
    global colormaps, _current_gamma
    
    if gamma is None:
        gamma = _current_gamma
    
    with _colormaps_lock:
        # Check underlying dict, not the lazy wrapper's __contains__
        if name not in dict.keys(colormaps):
            update_colormap(name, gamma)
        elif gamma != _current_gamma:
            # Regenerate if gamma changed
            update_colormap(name, gamma)


def generate_colormaps(gradients, gamma, colormap_names=None):
    """
    Generate colormaps from gradients.
    
    Args:
        gradients: Dictionary of gradient data
        gamma: Gamma correction value
        colormap_names: Optional list of specific colormap names to generate.
                       If None, generates all colormaps (legacy behavior).
    """
    global _current_gamma
    
    _current_gamma = gamma
    
    if colormap_names is None:
        # Legacy behavior: generate all
        for k, v in gradients.items():
            update_colormap(k, gamma)
    else:
        # Generate only specified colormaps
        for name in colormap_names:
            if name in gradients:
                update_colormap(name, gamma)


def _load_led_colormap_file(filepath):
    """Load a single .led.data colormap file. Returns (name, gradient_data) or None on error."""
    try:
        name_ext = os.path.splitext(os.path.basename(filepath))[0]
        name = os.path.splitext(name_ext)[0]
        gradient_data = np.loadtxt(filepath).tolist()
        return (name, gradient_data)
    except Exception as e:
        logger.warning(f"Loading colormap datafile {filepath} failed: {e}")
        return None


def _load_srgb_colormap_file(filepath, existing_names):
    """Load a single .sRGB.data colormap file. Returns (name, gradient_data) or None on error."""
    try:
        name_ext = os.path.splitext(os.path.basename(filepath))[0]
        name = os.path.splitext(name_ext)[0]
        if name in existing_names:
            name = name + "~"
        # sRGB files are gamma converted by **2.2 before loading into gradients
        gradient_data = np.loadtxt(filepath, converters=lambda x: float(x) ** 2.2).tolist()
        return (name, gradient_data)
    except Exception as e:
        logger.warning(f"Loading colormap datafile {filepath} failed: {e}")
        return None


def load_colormaps():
    """Load colormap files in parallel for faster startup."""
    gradients = {}
    
    # Load .led.data files in parallel
    led_files = glob.glob("Colormaps/*.led.data")
    if led_files:
        with ThreadPoolExecutor(max_workers=min(len(led_files), 8)) as executor:
            futures = {executor.submit(_load_led_colormap_file, f): f for f in led_files}
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    name, gradient_data = result
                    gradients[name] = gradient_data
    
    # Load .sRGB.data files in parallel
    srgb_files = glob.glob("Colormaps/*.sRGB.data")
    if srgb_files:
        with ThreadPoolExecutor(max_workers=min(len(srgb_files), 8)) as executor:
            futures = {executor.submit(_load_srgb_colormap_file, f, set(gradients.keys())): f for f in srgb_files}
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    name, gradient_data = result
                    gradients[name] = gradient_data

    return dict(sorted(gradients.items()))


def multicolor_to_gradient(multicolor_range, multicolor):
    m = zip(multicolor_range, multicolor)
    pos_next = None
    output = []
    for x in m:
        # range is 20 - 108
        pos1 = (x[0][0] - 20) / 88
        pos2 = (x[0][1] - 20) / 88
        color = x[1]

        output.append((pos1, color))
        output.append((pos2, color))

    # Warning: Overlaps can produce unintended results!  (Depending how you interpret it)
    # Lets return a valid gradient anyway
    output = sorted(output)
    return output


def update_multicolor(multicolor_range, multicolor):
    global gradients

    g = multicolor_to_gradient(multicolor_range, multicolor)
    if g is not None and len(g) >= 2:
        gradients["^Multicolor"] = g
    else:
        # default to some error color
        gradients["^Multicolor"] = [(15, 5, 5)]

    update_colormap("^Multicolor", 1)
