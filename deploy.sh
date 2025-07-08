cd frontend/
npm run build:deploy
cd ../backend/
./venv/bin/gunicorn --workers 1 --timeout 600 --bind 0.0.0.0:5000 --access-logfile - app:app