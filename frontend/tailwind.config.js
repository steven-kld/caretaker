import { defineConfig } from 'vite-plugin-windicss'

export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}"
  ],
  theme: {
    extend: {
      colors: {
        needleebg: '#ccd9ff',
        blobIndigo: 'rgba(71, 131, 199, 0.75)',
        blobLavender: 'rgba(140, 143, 241, 0.55)',
        blobSteel: 'rgba(226, 137, 205, 0.3)',
        blobIce: 'rgba(71, 131, 199, 0.55)',
        blobCloud: 'rgba(140, 143, 241, 0.95)',
      },
      animation: {
        blob1: "blob1 50s infinite ease-in-out",
        blob2: "blob2 60s infinite ease-in-out",
        blob3: "blob3 55s infinite ease-in-out",
        blob4: "blob4 48s infinite ease-in-out",
        blob5: "blob5 62s infinite ease-in-out",
      },
      keyframes: {
        blob1: {
          '0%':   { transform: 'translate(-100vw, -80vh) scale(1)' },
          '25%':  { transform: 'translate(40vw, -20vh) scale(1.2)' },
          '50%':  { transform: 'translate(80vw, 60vh) scale(0.9)' },
          '75%':  { transform: 'translate(-40vw, 70vh) scale(1.1)' },
          '100%': { transform: 'translate(-100vw, -80vh) scale(1)' },
        },
        blob2: {
          '0%':   { transform: 'translate(50vw, 10vh) scale(0.95)' },
          '25%':  { transform: 'translate(10vw, -40vh) scale(1.1)' },
          '50%':  { transform: 'translate(-30vw, 20vh) scale(1.05)' },
          '75%':  { transform: 'translate(40vw, 30vh) scale(1)' },
          '100%': { transform: 'translate(50vw, 10vh) scale(0.95)' },
        },
        blob3: {
          '0%':   { transform: 'translate(0vw, 0vh) scale(1)' },
          '20%':  { transform: 'translate(60vw, -60vh) scale(1.2)' },
          '40%':  { transform: 'translate(-40vw, 40vh) scale(0.85)' },
          '60%':  { transform: 'translate(30vw, 20vh) scale(1.1)' },
          '80%':  { transform: 'translate(-10vw, -50vh) scale(0.95)' },
          '100%': { transform: 'translate(0vw, 0vh) scale(1)' },
        },
        blob4: {
          '0%':   { transform: 'translate(-20vw, 20vh) scale(1)' },
          '25%':  { transform: 'translate(30vw, 30vh) scale(1.2)' },
          '50%':  { transform: 'translate(-50vw, -20vh) scale(0.9)' },
          '75%':  { transform: 'translate(40vw, -40vh) scale(1.1)' },
          '100%': { transform: 'translate(-20vw, 20vh) scale(1)' },
        },
        blob5: {
          '0%':   { transform: 'translate(10vw, -10vh) scale(1.1)' },
          '20%':  { transform: 'translate(-60vw, 50vh) scale(1)' },
          '40%':  { transform: 'translate(30vw, -30vh) scale(1.15)' },
          '60%':  { transform: 'translate(-40vw, 60vh) scale(0.85)' },
          '80%':  { transform: 'translate(60vw, -50vh) scale(1)' },
          '100%': { transform: 'translate(10vw, -10vh) scale(1.1)' },
        },
      },
    },
  },
  safelist: [
    'animate-blob1',
    'animate-blob2',
    'animate-blob3',
    'animate-blob4',
    'animate-blob5',
    'bg-needleebg',
  ],
  plugins: [],
}
