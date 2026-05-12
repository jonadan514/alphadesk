import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-noto-kr)", "var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      borderRadius: {
        DEFAULT: "0.625rem",
        sm: "0.375rem",
        md: "0.75rem",
        lg: "1rem",
        xl: "1.25rem",
        "2xl": "1.5rem",
      },
      colors: {
        surface: {
          DEFAULT: "var(--bg-base)",
          card:    "var(--bg-card)",
          inset:   "var(--bg-inset)",
          raised:  "var(--bg-raised)",
        },
        border: {
          DEFAULT: "var(--border)",
          dim:     "var(--border-dim)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          dim: "#22c55e",
          muted: "#166534",
        },
        warn:   "var(--warn)",
        danger: "var(--danger)",
      },
    },
  },
  plugins: [],
};

export default config;
