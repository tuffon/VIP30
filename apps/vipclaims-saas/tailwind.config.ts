import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      colors: {
        brand: {
          primary: "#2563EB",
          accent: "#A855F7",
          dark: "#020617",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;


