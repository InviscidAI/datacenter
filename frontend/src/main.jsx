import React from 'react';
import ReactDOM from 'react-dom/client';
import { MantineProvider } from '@mantine/core';
import App from './App.jsx';
import { theme } from './theme';
import '@mantine/core/styles.css'; // Import Mantine styles

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <MantineProvider theme={theme}>
      <App />
    </MantineProvider>
  </React.StrictMode>
);