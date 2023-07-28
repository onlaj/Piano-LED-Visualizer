const colors = require('tailwindcss/colors');

module.exports = {
  purge: {
    content: ['./templates/*.html', './static/*.{html,js}'],
      safelist: [
        'animate-spin'
      ]
  },
  darkMode: 'class', // or 'media' or 'class'
  theme: {
      colors: {
        // Build your palette here
        transparent: 'transparent',
        current: 'currentColor',
        gray: colors.zinc,
        red: colors.red,
        green: colors.emerald,
        blue: colors.sky,
        yellow: colors.amber,
      }
    },
  variants: {
    extend: {},
  },
  plugins: [],
}
