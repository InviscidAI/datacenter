// frontend/src/api.js
import axios from 'axios';

// Determine the correct base URLs based on environment
const SIM_API_BASE_URL = import.meta.env.PROD
  ? import.meta.env.VITE_SIM_API_URL_PRODUCTION
  : import.meta.env.VITE_SIM_API_URL;

const AI_API_BASE_URL = import.meta.env.PROD
  ? import.meta.env.VITE_AI_API_URL_PRODUCTION
  : import.meta.env.VITE_AI_API_URL;

export const simClient = axios.create({
  baseURL: `${SIM_API_BASE_URL}/api`,
});

export const aiClient = axios.create({
  baseURL: `${AI_API_BASE_URL}/api`,
});