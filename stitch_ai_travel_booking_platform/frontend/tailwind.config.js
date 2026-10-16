/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#18332d",
        ocean: "#176c67",
        sand: "#f7f5ef",
        sunset: "#dc805d",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["Georgia", "ui-serif", "serif"],
      },
      boxShadow: {
        card: "0 16px 50px rgba(23, 52, 46, .09)",
      },
    },
  },
  plugins: [],
};
