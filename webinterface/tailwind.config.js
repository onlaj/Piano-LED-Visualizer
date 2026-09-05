const colors = require('tailwindcss/colors');

module.exports = {
  // ui.js and friends build markup at runtime, so their classes have to be
  // scanned too or they get purged out of the bundle.
  content: [
    './templates/*.html',
    './static/*.{html,js}',
    './static/js/*.js',
  ],
  safelist: [
    'animate-spin',
    'top-1/2',
    'top-1/4',
    'right-2',
    'opacity-20',
    'opacity-30',
    '-translate-y-1/2'
  ],
  darkMode: 'class', // or 'media' or 'class'
  theme: {
    // These are aliases on top of the default palette, not a replacement for
    // it: setting `theme.colors` directly used to drop white, black, teal and
    // cyan, which the markup relies on for buttons, borders and focus rings.
    extend: {
      colors: {
        gray: colors.zinc,
        green: colors.emerald,
        blue: colors.sky,
        yellow: colors.amber,
      }
    }
  },
  variants: {
    extend: {},
  },
  plugins: [],
}
// npm run build   (from the webinterface/ directory)
