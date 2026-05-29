import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Navy — primary brand color (Citi/BNY/Amex style)
        navy: {
          DEFAULT: "#1B3A6B",
          50: "#EEF2FA",
          100: "#D6E0F0",
          200: "#AEC3E1",
          300: "#85A5D2",
          400: "#5D88C3",
          500: "#346AB4",
          600: "#1B3A6B", // main
          700: "#152D54",
          800: "#0F203D",
          900: "#0A1426",
          950: "#050A14",
        },
        
        // Slate — neutral grays for text and surfaces
        slate: {
          950: "#111827",
          900: "#1F2937",
          850: "#1E293B", // keep for dark mode fallback
          800: "#374151",
          750: "#4B5563",
          700: "#6B7280",
          600: "#9CA3AF",
          500: "#D1D5DB",
          400: "#E5E7EB",
          300: "#E8EDF5", // custom border color
          200: "#F1F3F7", // custom surface
          100: "#F8F9FB", // custom page bg
          50: "#FFFFFF",
        },
        
        // Primary — mapped to navy for consistency
        primary: {
          DEFAULT: "#1B3A6B",
          50: "#EEF2FA",
          100: "#D6E0F0",
          200: "#AEC3E1",
          300: "#85A5D2",
          400: "#5D88C3",
          500: "#346AB4",
          600: "#1B3A6B",
          700: "#152D54",
          800: "#0F203D",
          900: "#0A1426",
          950: "#050A14",
        },
        
        // Accent — cyan for highlights (charts, anomalies)
        accent: {
          DEFAULT: "#06B6D4",
          50: "#ECFEFF",
          100: "#CFFAFE",
          200: "#A5F3FC",
          300: "#67E8F9",
          400: "#22D3EE",
          500: "#06B6D4",
          600: "#0891B2",
          700: "#0E7490",
          800: "#155E75",
          900: "#164E63",
          950: "#083344",
        },
        
        // Semantic colors — adjusted for light theme
        success: "#1A6B3A",      // deeper green for finance
        warning: "#B87B0A",      // amber for anomalies
        danger: "#DC2626",       // red for errors
        info: "#1B3A6B",         // navy for info
        
        // Surface colors — light theme
        surface: {
          DEFAULT: "#FFFFFF",      // main background
          elevated: "#F8F9FB",     // cards, panels
          overlay: "#F1F3F7",      // inputs, hover
          border: "#E8EDF5",       // borders, dividers
        },
      },
      
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      
      boxShadow: {
        // Subtle shadows for light theme (no glows)
        sm: "0 1px 2px 0 rgba(27, 58, 107, 0.05)",
        DEFAULT: "0 1px 3px 0 rgba(27, 58, 107, 0.08), 0 1px 2px -1px rgba(27, 58, 107, 0.08)",
        md: "0 4px 6px -1px rgba(27, 58, 107, 0.08), 0 2px 4px -2px rgba(27, 58, 107, 0.08)",
        lg: "0 10px 15px -3px rgba(27, 58, 107, 0.08), 0 4px 6px -4px rgba(27, 58, 107, 0.08)",
        xl: "0 20px 25px -5px rgba(27, 58, 107, 0.08), 0 8px 10px -6px rgba(27, 58, 107, 0.08)",
        // Keep glow for dark mode only (optional)
        glow: "0 0 20px rgba(27, 58, 107, 0.15)",
        "glow-sm": "0 0 10px rgba(27, 58, 107, 0.1)",
      },
      
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        shimmer: "shimmer 2s linear infinite",
        "fade-in": "fadeIn 0.3s ease-out",
        "slide-up": "slideUp 0.4s ease-out",
        typing: "typing 1.5s ease-in-out infinite",
      },
      
      keyframes: {
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        fadeIn: {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        typing: {
          "0%, 100%": { opacity: "0.3" },
          "50%": { opacity: "1" },
        },
      },
      
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        // Subtle mesh for light theme
        mesh: "radial-gradient(ellipse at top, rgba(27,58,107,0.03) 0%, transparent 50%), radial-gradient(ellipse at bottom right, rgba(6,182,212,0.02) 0%, transparent 50%)",
      },
    },
  },
  plugins: [],
};

export default config;
