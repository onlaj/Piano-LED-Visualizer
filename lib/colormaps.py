import numpy as np
import os
import glob
from lib.log_setup import logger

colormaps = {}
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
    global colormaps, colormaps_preview, gradients

    try:
        colormaps[name] = gradient_to_cmaplut(gradients[name], gamma)
        colormaps_preview[name] = gradient_to_cmaplut(gradients[name], 2.2, 64)
    except Exception as e:
        logger.warning(f"Loading colormap {name} failed: {e}")


def generate_colormaps(gradients, gamma):
    global colorsmaps, colorsmaps_preview

    for k, v in gradients.items():
        update_colormap(k, gamma)


def load_colormaps():
    gradients = {}

    files = glob.glob("Colormaps/*.led.data")
    for f in files:
        try:
            name_ext = os.path.splitext(os.path.basename(f))[0]
            name = os.path.splitext(name_ext)[0]
            gradients[name] = np.loadtxt(f).tolist()
        except Exception as e:
            logger.warning(f"Loading colormap datafile {f} failed: {e}")

    # sRGB files are gamma converted by **2.2 before loading into gradients to keep with ws2812's intensity-based color space
    files = glob.glob("Colormaps/*.sRGB.data")
    for f in files:
        try:
            name_ext = os.path.splitext(os.path.basename(f))[0]
            name = os.path.splitext(name_ext)[0]
            if name in gradients:
                name = name + "~"
            gradients[name] = np.loadtxt(f, converters=lambda x: float(x) ** 2.2).tolist()
        except Exception as e:
            logger.warning(f"Loading colormap datafile {f} failed: {e}")

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
