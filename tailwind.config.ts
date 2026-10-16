import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: {
          950: '#08090c',
          900: '#0d0f14',
          850: '#12151c',
          800: '#171b24',
          700: '#232936',
          600: '#333b4d',
        },
        signal: {
          watch: '#e0b341',
          notable: '#e07a3f',
          extreme: '#e05252',
          calm: '#4fb3a5',
        },
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
};

export default config;
