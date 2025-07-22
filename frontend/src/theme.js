// src/theme.js

import { createTheme } from '@mantine/core';

export const theme = createTheme({
  /** Controls color scheme for all components */
  primaryColor: 'shamrock',

  /** Default fonts for headings and other text */
  fontFamily: 'Lato, sans-serif',
  headings: {
    fontFamily: 'Montserrat, sans-serif',
  },

  /** Custom colors from your design system */
  colors: {
    'shamrock': [
      "#ecfbf1",
      "#e3f8ea",
      "#c5f1d3",
      "#a2e8b9",
      "#7fde9f",
      "#66d88c",
      "#43d270", // This will be the main shade
      "#3cbd65",
      "#329e54",
      "#287e43"
    ],
    'iris': [
      "#f7f5ff",
      "#f2f0ff",
      "#e5e1ff",
      "#d3cfff",
      "#c2beff",
      "#b0aeff",
      "#ab9eff", // Main shade
      "#9a8ee6",
      "#897ecc",
      "#8077bf"
    ],
    'orange': [
      "#fef0ea",
      "#fee9e0",
      "#fdd1bf",
      "#fbb89e",
      "#faa07e",
      "#f9875d",
      "#f96c30", // Main shade
      "#e0612b",
      "#c75626",
      "#bb5124"
    ],
    'grey': [
      "#f8f9fa",
      "#f1f3f5",
      "#e9ecef",
      "#dee2e6",
      "#ced4da",
      "#adb5bd",
      "#868e96", // Main shade
      "#495057",
      "#343a40",
      "#212529"
    ],
  },
});