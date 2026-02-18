import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["IBM Plex Sans", "ui-sans-serif", "sans-serif"],
      },
      colors: {
        brand: {
          primary: "#0F3A5F",
          accent: "#2E5E8A",
          dark: "#0B1623",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;


