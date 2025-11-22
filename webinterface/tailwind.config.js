const colors = require('tailwindcss/colors');

module.exports = {
  content: ['./templates/*.html', './static/*.{html,js}'],
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
// npx tailwindcss build static/styles.css -o static/tailwind.css --minify