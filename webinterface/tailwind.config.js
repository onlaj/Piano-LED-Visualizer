const colors = require('tailwindcss/colors');

module.exports = {
  darkMode: 'class', // or 'media' or 'class'
  theme: {
      colors: {
        // Build your palette here
        transparent: 'transparent',
        current: 'currentColor',
        white: colors.white,
        black: colors.black,
        gray: colors.zinc,
        red: colors.red,
        green: colors.emerald,
        blue: colors.sky,
        yellow: colors.amber,
        teal: colors.teal,
        cyan: colors.cyan,
      }
    },
  plugins: [],
}
// Tailwind v4 loads this file explicitly via @config in static/styles.css.
