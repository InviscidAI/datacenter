// frontend/src/api.js
import axios from 'axios';

// Vite exposes env variables on the `import.meta.env` object.
// VITE_DEV is true when running `npm run dev`, false when running `npm run build`.
export const API_BASE_URL = import.meta.env.PROD
  ? import.meta.env.VITE_API_URL_PRODUCTION
  : import.meta.env.VITE_API_URL;

const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api`,
});

export default apiClient;