# CabPool

CabPool is a command-line prototype that groups hostel students travelling to the same destination around the same time. It uses overlapping time-flexibility windows, road distances from Bennett University, and a Rs. 10/km fare to estimate each passenger's share.

## Features

- Collects and validates names, destinations, departure times, and flexibility windows up to 360 minutes.
- Groups compatible requests by destination, with a default capacity of four passengers.
- Uses a bundled list of 1,000 nearby places and calculates their road distance from Bennett University.
- Asks for a manual road distance when a destination is not in the bundled list or routing is unavailable.
- Calculates each passenger's share at Rs. 10/km and estimated savings against solo rides.
- Saves ride requests to `requests.csv` and matching results to `results.json`.

## Requirements

Python 3.8 or newer. The project uses only the Python standard library.

## Run

```bash
python cabpool_5_methods.py
```

Choose **1. Add ride request** to enter requests, then **3. Match and show results** to form cab groups. Enter a place name from `places_within_400_km_of_bennett_university.txt`, or its list number. CabPool looks up its road distance; for a place outside the list, it asks you to enter the distance in kilometres. Time windows can cross midnight. Existing requests are loaded from `requests.csv` when the program starts.

The origin is Bennett University, Greater Noida. Fares are calculated as `distance in km × Rs. 10`, then divided evenly among passengers. Cab capacity is four.

## How matching works

Requests are grouped by destination and sorted by preferred departure time. The matcher starts with the earliest request, then adds requests whose time windows overlap the group's common window until the cab is full or no compatible request remains. The suggested departure is the midpoint of the final shared window. Requests that cannot be grouped are listed as unmatched.

## Project context

CabPool was proposed as a way to reduce separate cab bookings and simplify coordination before semester breaks. The prototype focuses on request validation, greedy matching, fare calculation, local file storage, and readable results.

## Files

- `cabpool_5_methods.py` — the command-line application
- `places_within_400_km_of_bennett_university.txt` — the 1,000-place destination list
- `index.html` — project landing page
- `requests.csv` and `results.json` — generated at runtime in the current directory
- `distance_cache.json` — map matches and road distances cached beside the program

## Distance lookup and attribution

Catalog entries are geocoded with OpenStreetMap Nominatim, then routed with OSRM against OpenStreetMap road data. Distances are from Bennett University's campus transport-road coordinates to the matched place point; they may differ from a specific building entrance or live driving conditions. Results are cached to avoid repeat lookups. If a place is absent from the list or a route cannot be calculated, enter its road distance manually.

The public Nominatim and OSRM demo services are rate-limited and best-effort. CabPool spaces map requests and caches results. To change providers without editing the code, set `CABPOOL_GEOCODER_URL` to a compatible Nominatim search endpoint and `CABPOOL_ROUTER_URL` to a compatible OSRM driving route endpoint. Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright); geocoding by [Nominatim](https://nominatim.org/); routing by [OSRM](https://project-osrm.org/).

## License

No license has been specified yet.
