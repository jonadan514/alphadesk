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
        sans: ["ui-monospace", "SF Mono", "Cascadia Code", "Roboto Mono", "var(--font-noto-kr)", "var(--font-inter)", "ui-sans-serif", "system-ui", "monospace"],
      },
      borderRadius: {
        DEFAULT: "0px",
        sm: "0px",
        md: "0px",
        lg: "0px",
        xl: "0px",
        "2xl": "0px",
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
          ctrl:    "var(--border-ctrl)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          dim: "#c98a2e",
          muted: "#4a3410",
        },
        good:   "var(--good)",
        info:   "var(--info)",
        num:    "var(--num)",
        warn:   "var(--warn)",
        danger: "var(--danger)",
      },
    },
  },
  plugins: [],
};

export default config;
