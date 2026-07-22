import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          50: "#f7f8fa",
          100: "#eef1f5",
          200: "#d8dee8",
          300: "#b6c0ce",
          400: "#8997aa",
          500: "#66758a",
          600: "#4f5c6f",
          700: "#384557",
          800: "#273244",
          900: "#172132"
        }
      },
      boxShadow: {
        soft: "0 10px 30px rgba(23, 33, 50, 0.08)"
      }
    }
  },
  plugins: []
};

export default config;
