/** @type {import('tailwindcss').Config} */
module.exports = {
  // Scan tous les templates et JS pour purger les classes inutilisées
  content: [
    "./web/templates/**/*.html",
    "./web/static/js/**/*.js",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        accent: {
          blue:   "#6366f1",
          green:  "#10b981",
          red:    "#f43f5e",
          orange: "#f59e0b",
          purple: "#a855f7",
        },
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
      },
    },
  },
  plugins: [],
};
