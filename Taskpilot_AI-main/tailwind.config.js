/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./index.tsx",
    "./App.tsx",
    "./components/**/*.{js,ts,jsx,tsx}",
    "./services/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      animation: {
        'gentle-shake': 'gentle-shake 0.5s ease-in-out',
      },
      keyframes: {
        'gentle-shake': {
          '0%, 100%': { transform: 'translateX(0)' },
          '10%': { transform: 'translateX(-2px) rotate(-1deg)' },
          '20%': { transform: 'translateX(2px) rotate(1deg)' },
          '30%': { transform: 'translateX(-2px) rotate(-1deg)' },
          '40%': { transform: 'translateX(2px) rotate(1deg)' },
          '50%': { transform: 'translateX(0)' },
        },
      },
    },
  },
  plugins: [],
}
