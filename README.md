# Datacenter Frontend

This repository contains only the React frontend for the datacenter project. The backend services have moved to their own repository.

## Setup

Run `./setup.sh` to install dependencies.

```
./setup.sh
```

## Development

The frontend communicates with two backend URLs. Edit `frontend/.env` to adjust
`VITE_AI_API_URL` (for image processing and chat) and `VITE_SIM_API_URL`
(for simulation and optimization). Production builds use the corresponding
`*_PRODUCTION` variables.

From the `frontend` directory you can start the dev server:

```
cd frontend
npm run dev
```

## Building for Production

Use `./deploy.sh` to build the frontend. The compiled assets are written to `frontend/dist`.

```
./deploy.sh
```

## Serving the Build

After building, you can start a simple Express server to serve the static files:

```
npm start
```

The server listens on port `3000` by default and serves the files from `frontend/dist`.
