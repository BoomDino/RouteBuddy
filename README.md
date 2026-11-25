# CabPool

CabPool is a command-line prototype that groups hostel students travelling to the same station or airport around the same time. It uses overlapping time-flexibility windows to form groups, then splits a sample cab fare evenly.

## Features

- Collects and validates names, destinations, departure times, and flexibility windows.
- Groups compatible requests by destination, with a default capacity of four passengers.
- Calculates each passenger's share and estimated savings against solo rides.
- Saves ride requests to `requests.csv` and matching results to `results.json`.
- Includes sample requests for trying the matching flow.

## Requirements

Python 3.8 or newer. The project uses only the Python standard library.

## Run

```bash
python cabpool_5_methods.py
```

Choose **4. Load sample data**, then **3. Match and show results** to see a sample run. Choose **1. Add ride request** to enter a request manually.

The default fare is Rs. 600 per cab and the default capacity is four passengers. Both are set in `main()`.

## How matching works

Requests are grouped by destination and sorted by preferred departure time. The matcher starts with the earliest request, then adds requests whose time windows overlap the group's common window until the cab is full or no compatible request remains. The suggested departure is the midpoint of the final shared window. Requests that cannot be grouped are listed as unmatched.

## Project context

CabPool was proposed as a way to reduce separate cab bookings and simplify coordination before semester breaks. The prototype focuses on request validation, greedy matching, fare calculation, local file storage, and readable results.

## Files

- `cabpool_5_methods.py` — the command-line application
- `index.html` — project landing page
- `requests.csv` and `results.json` — generated at runtime in the current directory

## License

No license has been specified yet.
