const colors = require('tailwindcss/colors');

module.exports = {
  purge: [
    './templates/*.html'
  ],
  darkMode: 'class', // or 'media' or 'class'
  theme: {
      colors: {
        // Build your palette here
        transparent: 'transparent',
        current: 'currentColor',
        gray: colors.gray,
        red: colors.red,
        green: colors.emerald,
        blue: colors.lightBlue,
        yellow: colors.amber,
      }
    },
  variants: {
    extend: {},
  },
  plugins: [],
}
