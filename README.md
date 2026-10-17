# Weather-Aware Truck Routing

A React + Django app that helps a truck driver pick a route by the weather it will meet. Enter an origin, a destination, a departure time and the load weight; the app finds up to three truck routes, reads the hourly forecast at checkpoints along each one for the hour the truck gets there, scores the risk with the load rules, and recommends a route. A map shows the routes, the checkpoints with their ETAs and risk, and a weather heatmap of the whole corridor with a 0–48 hour slider.

Live app: https://diego-burbano-truck-routing.vercel.app
API health check: https://truck-route-planner-api-qfz4.onrender.com/api/health/

The API runs on Render's free tier, which sleeps after 15 minutes without traffic, so the first trip after a quiet spell can take about a minute. Later ones take 10 to 15 seconds.

## How a trip is planned

1. **Routes.** The trip form posts to `POST /api/trips/plan/`. Django geocodes both places with OpenRouteService, keeping to towns, addresses and points of interest (otherwise "Boise, ID" resolves to Boise County, in the mountains). OpenRouteService only starts a route within 350 m of a road, so both ends are first moved to the nearest truck road. Django then asks for heavy-goods-vehicle routes with the load as a weight restriction: the recommended route, the shortest one, and detours through points set off to each side of the main route at a third and two thirds of the way. An alternative more than 1.5 times slower than the main route, or sharing more than 85% of its road with a route already kept, is dropped, and up to three routes are kept. A detour is named after the longest road it takes that the main route does not ("Via I 55"). When a trip has no third route that is really different, the app shows fewer rather than near copies.
2. **Checkpoints.** Each route gets a checkpoint at the start, every 10, 25 or 50 miles, and at the destination. The step follows the length of the main route (up to 200 miles: 10; up to 600: 25; longer: 50) and is the same for all routes so they can be compared; the form can also fix it. The ETA of each checkpoint comes from the distance and duration OpenRouteService reports for every step of the route, so a slow stretch through a city delays every checkpoint after it. A regular checkpoint less than a mile from the destination is merged into it.
3. **Forecast.** The plan response carries the routes, the Open-Meteo URLs for all their checkpoints over the forecast window, and a signed ticket. The browser fetches those URLs itself and posts the answers with the ticket to `POST /api/trips/assess/`.
4. **Risk and ranking.** Django checks the ticket's signature, reads each checkpoint's weather for the hour nearest its ETA, classifies it, works out the risk of every checkpoint for each of the 49 hours of the heatmap, ranks the routes and sends back the result.

### Why the browser fetches the forecast

Open-Meteo's free tier limits requests per IP address, and cloud hosts share their outbound addresses among many customers. On Render the shared address had used up the day's quota before this app asked for anything, so every forecast came back refused. Fetching from the browser puts each visitor on their own quota. The server still decides everything that matters: it builds the checkpoints and the URLs, and the ticket it signs (checkpoints, ETAs, load and forecast window, valid for an hour) means the assessment can only run on checkpoints the server produced. The forecast values themselves come from the visitor's browser, which only affects that visitor's own result. Nothing is stored between the two calls.

## Decisions on the rules

**Risk levels.** The brief's table lists shared limits in two bands (0.25 in/h of rain is in both Moderate and High). A reading on a limit takes the higher band, which is what the wind row already does with 25 mph. No Travel starts strictly above 1.00 in/h of rain and 3.0 in/h of snow, as written, but at 55 mph of wind, also as written. Rain includes Open-Meteo's showers, since convective bursts are where heavy rain comes from. The worst of wind, rain and snow sets the level.

**Load rules.** Wind of 45 mph or more with more than 30,000 lb is No Travel. Wind of 35 mph or more with more than 40,000 lb is at least Severe. A load rule never lowers a worse level that rain or snow already set.

**Missing data.** A checkpoint whose forecast has no wind, rain or snow is shown as "No data". It stays out of the average, and its miles are listed as "No data" so the miles per level still add up to the trip.

**Ranking.** A checkpoint's reading counts for the road from it to the next checkpoint, so the destination adds no miles. Routes are ordered by fewest Severe miles, then fewest High miles, then lowest average risk (Low = 0 to No Travel = 4, over the checkpoints with data), then shortest time. The brief says nothing about No Travel; here a route that meets No Travel anywhere goes last and is never recommended, and when every route does, nothing is recommended. On a full tie the routing order wins.

**Heatmap.** The slider shows every checkpoint of every route at one hour, from the departure hour to 48 hours later, classified with the same load rules. The route colors do not move with it: they keep showing what the truck meets at its own arrival times. A ring marks where the selected route's truck is at that hour.

**Departure window.** Departures are accepted from the start of the current hour to seven days ahead, which keeps the longest haul plus the 48-hour slider inside Open-Meteo's 16-day forecast.

## Project layout

```
backend/                       Django 5.2 + Django REST Framework, Python 3.11
  config/settings.py           settings read from the environment
  trips/views.py               POST /api/trips/plan/ and POST /api/trips/assess/
  trips/serializers.py         input validation
  trips/services/
    ors.py                     OpenRouteService client and its errors
    geocoding.py               place name to coordinates
    routing.py                 the three route options
    checkpoints.py             checkpoint spacing, positions and ETAs
    weather.py                 Open-Meteo URLs, reading the answers, the hour at an ETA
    risk.py                    risk levels and load rules
    ranking.py                 miles per level, average risk, ranking
    planning.py                the two steps of a plan and the signed ticket
frontend/                      React 19 + Vite, Leaflet for the map
  src/api.js                   the three requests of a plan
  src/TripForm.jsx             the form
  src/RouteList.jsx            ranked routes with their risk strips
  src/RouteMap.jsx             map, heatmap and slider
  src/geometry.js              route cuts at checkpoints, truck position
  src/Checkpoints.jsx          checkpoint table
render.yaml                    Render Blueprint for the API
```

## Running it locally

You need Python 3.11, Node 22.12 or later, and an OpenRouteService key (free at https://openrouteservice.org).

```
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # then set ORS_API_KEY
python manage.py runserver
```

```
cd frontend
npm install
cp .env.example .env          # VITE_API_URL=http://localhost:8000
npm run dev
```

Then open http://localhost:5173.

## Tests

```
cd backend && pytest          # 132 tests
cd frontend && npm test       # 35 tests
cd frontend && npm run lint
```

The backend tests cover every threshold of the risk table and the load rules at their edges, the ranking criteria one at a time, checkpoint placement and ETAs, the OpenRouteService client against mocked responses, the Open-Meteo URLs and how their answers are read, input validation, the signed ticket and a whole trip through both endpoints. The frontend tests cover the formatting, the route cuts and the truck position, the form, the route list and why a route was recommended, the checkpoint table, the API calls and every state of the page, from empty to an outage. They run in the America/Chicago time zone, so a time sent as wall-clock instead of as an instant would fail.

## Deployment

- **API on Render.** `render.yaml` describes the service: gunicorn, Python 3.11.13, `DJANGO_DEBUG=0`, a generated secret key, and the Vercel addresses allowed by CORS. The OpenRouteService key is entered in the Render dashboard, never in the repository. With DEBUG off the app refuses to start without a real secret key, and Render's own hostname is allowed automatically.
- **Frontend on Vercel.** The project's root is `frontend`, Vite is detected on its own, and `VITE_API_URL` points at the Render service. Vite builds that value into the bundle, so changing it needs a new deploy.

## Limits

- OpenRouteService's free key has small daily quotas per service (100 geocoding requests a day at the time of writing), and a reached quota comes back as a 502 with OpenRouteService's message. A plan makes up to ten calls (two geocodes, two snaps, the main and shortest routes and up to four detours); each server process caches geocodes for a day and routes and snaps for an hour, so repeating a trip costs nothing.
- Checkpoints are 10 to 50 miles apart, so weather between two checkpoints is represented by the one before it.
- The forecast is hourly. A checkpoint reached at 2:40 reads the 3:00 forecast.
