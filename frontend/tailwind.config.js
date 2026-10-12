/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        sandalwood: '#FFF8ED',
        ivory: '#FFFCF6',
        ink: '#30241F',
        'muted-brown': '#806D61',
        sand: '#EADBC5',
        maroon: {
          50: '#FDF4F4',
          100: '#F8E4E5',
          200: '#F2C8CB',
          600: '#7E252D',
          700: '#641E24',
          800: '#4E161B',
          900: '#380E13',
          950: '#28080C',
        },
        terracotta: {
          50: '#FDF6F4',
          100: '#FBE9E3',
          200: '#F6CFC3',
          400: '#CB694A',
          500: '#B95332',
          600: '#9E4326',
          700: '#7E331B',
        },
        saffron: {
          50: '#FEFBF2',
          100: '#FCF3DA',
          200: '#F8E4AF',
          400: '#E3B24F',
          500: '#D9A441',
          600: '#BD892B',
          700: '#94691B',
        },
        forest: {
          50: '#F2F8F5',
          100: '#E0EFE8',
          200: '#BED9CD',
          500: '#347558',
          600: '#285943',
          700: '#1D4332',
          800: '#153224',
        },
      },
      fontFamily: {
        serif: ['Lora', 'Playfair Display', 'Georgia', 'serif'],
        sans: ['Plus Jakarta Sans', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        'heritage-sm': '0 1px 3px rgba(48, 36, 31, 0.05), 0 1px 2px rgba(48, 36, 31, 0.03)',
        'heritage': '0 4px 14px -2px rgba(100, 30, 36, 0.06), 0 2px 6px -1px rgba(48, 36, 31, 0.04)',
        'heritage-lg': '0 10px 25px -4px rgba(100, 30, 36, 0.08), 0 4px 10px -2px rgba(48, 36, 31, 0.04)',
      },
    },
  },
  plugins: [],
}
