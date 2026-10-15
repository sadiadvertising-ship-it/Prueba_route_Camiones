# Weather-Aware Truck Routing

React + Django app that compares three routes for a truck trip and recommends the safest one, based on the weather forecast along each route, the load weight and the travel time.

## Stack

- Backend: Django 5.2 + Django REST Framework (Python 3.11)
- Frontend: React 19 + Vite
- Routing and geocoding: OpenRouteService
- Weather: Open-Meteo

## Running locally

Backend:

```
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # add your OpenRouteService key
python manage.py runserver
```

Frontend:

```
cd frontend
npm install
cp .env.example .env
npm run dev
```

Tests: `cd backend && pytest`
