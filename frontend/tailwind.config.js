/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#1A1410",
        accent: "#D4870A",
        detail: "#C8C8C0",
      },
      fontFamily: {
        tab: ["'Space Mono'", "monospace"],
        ui: ["Inter", "sans-serif"],
      },
    },
  },
  plugins: [],
};
