/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Warm, spiritual color palette
        primary: {
          50: "#faf5f0",
          100: "#f3e8db",
          200: "#e6d0b8",
          300: "#d5b08d",
          400: "#c48d62",
          500: "#b87444",
          600: "#a35f38",
          700: "#874a30",
          800: "#6e3d2c",
          900: "#5b3427",
        },
        accent: {
          50: "#f0f7f4",
          100: "#dbebe3",
          200: "#bad7ca",
          300: "#8fbbaa",
          400: "#639a86",
          500: "#467d6a",
          600: "#356454",
          700: "#2c5145",
          800: "#264239",
          900: "#213730",
        },
      },
      fontFamily: {
        serif: ["Georgia", "Cambria", "Times New Roman", "serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
