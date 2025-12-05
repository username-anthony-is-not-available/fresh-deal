export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f0fdf4',
          100: '#dcfce7',
          500: '#22c55e', // Green-500
          600: '#16a34a',
          700: '#15803d',
        },
        accent: {
          500: '#f97316', // Orange-500
          600: '#ea580c',
        }
      }
    },
  },
  plugins: [],
}
