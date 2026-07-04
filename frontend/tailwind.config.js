/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{vue,ts}"],
  theme: {
    extend: {
      colors: {
        fm: {
          bg: "#05070b",
          panel: "#0f141c",
          panelSoft: "#171f2a",
          text: "#e8edf5",
          muted: "#95a2b8",
          accent: "#4dd0e1",
          warn: "#f9a825",
          danger: "#ef5350",
          success: "#66bb6a"
        }
      },
      boxShadow: {
        panel: "0 12px 40px rgba(0, 0, 0, 0.35)",
      },
    },
  },
  plugins: [],
};
