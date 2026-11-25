"""
CabPool - Station/Airport Cab-Pool Matcher (divided into 5 methods)

  1. take_input()         - Input and Validation
  2. match_requests()     - Matching Engine (greedy grouping)
  3. calculate_fares()    - Fare Calculator
  4. file_storage(mode)   - File Storage (CSV for requests, JSON for results)
  5. display_results()    - Output Display

Run:  python cabpool_5_methods.py
"""

import csv
import json
import os
import re
import time
import unicodedata
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REQUESTS_FILE = "requests.csv"
RESULTS_FILE = "results.json"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLACES_FILE = os.path.join(SCRIPT_DIR, "places_within_400_km_of_bennett_university.txt")
DISTANCE_CACHE_FILE = os.path.join(SCRIPT_DIR, "distance_cache.json")
ORIGIN_NAME = "Bennett University, Greater Noida"
ORIGIN_LATITUDE = 28.449532
ORIGIN_LONGITUDE = 77.581288
FARE_PER_KM = 10
OSRM_ROUTE_URL = os.environ.get(
    "CABPOOL_ROUTER_URL", "https://router.project-osrm.org/route/v1/driving"
)
NOMINATIM_URL = os.environ.get(
    "CABPOOL_GEOCODER_URL", "https://nominatim.openstreetmap.org/search"
)
_last_map_request = 0


def normalize_place(text):
    """Normalize place names for case- and punctuation-insensitive matching."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", ascii_text.lower())


def wait_for_map_service():
    """Keep requests to the public geocoder/router within their demo limits."""
    global _last_map_request
    wait = 1.1 - (time.monotonic() - _last_map_request)
    if wait > 0:
        time.sleep(wait)
    _last_map_request = time.monotonic()


def get_json(url):
    wait_for_map_service()
    request = Request(url, headers={
        "User-Agent": "CabPool/1.0 (student cab-pooling project)",
        "Accept": "application/json",
    })
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def load_places():
    """Read numbered place names from the supplied 1,000-place text list."""
    places = []
    current_section = "Places"
    section_header = re.compile(r"^\s*\d+\.\s+(.+?)\s+\(\d+\s*-\s*\d+\)\s*$")
    subgroup_header = re.compile(r"^--\s*(.+?)\s*--$")
    numbered_place = re.compile(r"^\s*(\d{1,4})\.\s+(.+?)\s*$")

    with open(PLACES_FILE, encoding="utf-8") as file:
        for line in file:
            match = section_header.match(line)
            if match:
                current_section = match.group(1)
                continue
            match = subgroup_header.match(line.strip())
            if match and set(match.group(1).replace(" ", "")) != {"-"}:
                current_section = match.group(1)
                continue
            match = numbered_place.match(line)
            if match and 1 <= int(match.group(1)) <= 1000:
                places.append({
                    "number": int(match.group(1)),
                    "name": match.group(2).strip(),
                    "section": current_section,
                })
    if len(places) != 1000:
        raise ValueError(f"Expected 1,000 places in {PLACES_FILE}, found {len(places)}")
    return places


def to_minutes(text):
    """'18:30' or '6:30 PM' -> minutes after midnight, or None if invalid."""
    text = text.strip().upper()
    suffix = text[-2:] if text[-2:] in ("AM", "PM") else None
    if suffix:
        text = text[:-2].strip()
    parts = text.split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        return None
    hour, minute = int(parts[0]), int(parts[1])
    if minute > 59:
        return None
    if suffix:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if suffix == "PM" else 0)
    elif hour > 23:
        return None
    return hour * 60 + minute


def to_str(minutes):
    """Minutes after midnight -> 'HH:MM'."""
    minutes = int(round(minutes)) % (24 * 60)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


class CabPool:
    def __init__(self, capacity=4, fare_per_km=FARE_PER_KM):
        self.capacity = capacity
        self.fare_per_km = fare_per_km
        self.requests = []
        self.cabs = []
        self.unmatched = []
        self.places = load_places()
        try:
            with open(DISTANCE_CACHE_FILE, encoding="utf-8") as file:
                self.distance_cache = json.load(file)
        except (OSError, json.JSONDecodeError):
            self.distance_cache = {}

    def choose_catalog_place(self, destination):
        """Return the selected catalog place, or None when it is not listed."""
        query = normalize_place(destination)
        if not query:
            return None
        if query.isdigit():
            for place in self.places:
                if place["number"] == int(query):
                    return place
        exact = [place for place in self.places
                 if (normalize_place(place["name"]) == query
                     or normalize_place(place["name"].split(",", 1)[0]) == query)]
        matches = exact or [place for place in self.places
                            if query in normalize_place(place["name"])]
        if len(matches) == 1:
            return matches[0]
        if not matches or len(matches) > 8:
            return None

        print("Matching places in the Bennett University list:")
        for index, place in enumerate(matches, 1):
            print(f"  {index}. {place['name']}")
        while True:
            choice = input("Choose a place number, or press Enter if none match: ").strip()
            if not choice:
                return None
            if choice.isdigit() and 1 <= int(choice) <= len(matches):
                return matches[int(choice) - 1]
            print("  ! Choose one of the listed numbers or press Enter.")

    def route_distance(self, place):
        """Return the road distance from Bennett to a catalog place in km."""
        cache_key = place["name"]
        if cache_key in self.distance_cache:
            cached = self.distance_cache[cache_key]
            print(f"  Map location: {cached.get('map_match', place['name'])}")
            return cached["distance_km"], "OpenStreetMap route (cached)"

        search_url = NOMINATIM_URL + "?" + urlencode({
            "q": place["name"] + ", India",
            "format": "jsonv2",
            "limit": 1,
        })
        matches = get_json(search_url)
        if not matches:
            raise ValueError("the place could not be found on the map")

        latitude = float(matches[0]["lat"])
        longitude = float(matches[0]["lon"])
        route_url = (
            f"{OSRM_ROUTE_URL}/{ORIGIN_LONGITUDE},{ORIGIN_LATITUDE};"
            f"{longitude},{latitude}?overview=false"
        )
        route_result = get_json(route_url)
        if route_result.get("code") != "Ok" or not route_result.get("routes"):
            raise ValueError("no driving route was returned")

        distance_km = round(route_result["routes"][0]["distance"] / 1000, 1)
        self.distance_cache[cache_key] = {
            "distance_km": distance_km,
            "latitude": latitude,
            "longitude": longitude,
            "map_match": matches[0].get("display_name", place["name"]),
        }
        try:
            with open(DISTANCE_CACHE_FILE, "w", encoding="utf-8") as file:
                json.dump(self.distance_cache, file, indent=2, ensure_ascii=False)
        except OSError:
            print("  Could not save the map cache; the distance is still available.")
        print(f"  Map location: {self.distance_cache[cache_key]['map_match']}")
        return distance_km, "OpenStreetMap route"

    @staticmethod
    def ask_manual_distance(destination):
        """Ask for the road distance when the place is not in the supplied list."""
        while True:
            value = input(
                f"Road distance from {ORIGIN_NAME} to {destination} in km: "
            ).strip()
            try:
                distance = float(value)
                if distance >= 0:
                    return round(distance, 1), "manually entered"
            except ValueError:
                pass
            print("  ! Enter a non-negative distance in kilometres.")

    def resolve_destination(self, destination):
        """Use routed distance for catalog places and manual distance otherwise."""
        place = self.choose_catalog_place(destination)
        if place is None:
            print("Place not found in the supplied list; use its road distance manually.")
            return destination, *self.ask_manual_distance(destination)

        canonical_name = place["name"]
        try:
            distance_km, source = self.route_distance(place)
        except (URLError, TimeoutError, ValueError, KeyError, OSError, json.JSONDecodeError) as error:
            print(f"Could not calculate the map route ({error}).")
            distance_km, source = self.ask_manual_distance(canonical_name)
        print(f"Distance from Bennett University to {canonical_name}: {distance_km:.1f} km.")
        return canonical_name, distance_km, source

    def resolve_missing_distances(self):
        """Resolve older saved requests that do not yet have a distance."""
        changed = False
        for request in self.requests:
            if request.get("distance_km") is None:
                (request["destination"], request["distance_km"],
                 request["distance_source"]) = self.resolve_destination(request["destination"])
                changed = True
        if changed:
            self.file_storage("save")

    # METHOD 1: Input and Validation
    def take_input(self):
        """Ask for one ride request, validate every field, and store it."""
        print("\n--- New ride request ---")

        while True:
            name = input("Name: ").strip()
            if name and all(c.isalpha() or c in " .'-" for c in name):
                break
            print("  ! Enter a valid name (letters only).")

        while True:
            destination_input = " ".join(input("Destination: ").split())
            if (len(destination_input) >= 2
                    or (destination_input.isdigit()
                        and 1 <= int(destination_input) <= 1000)):
                break
            print("  ! Enter a valid destination.")

        destination, distance_km, distance_source = self.resolve_destination(destination_input)

        while True:
            time = to_minutes(input("Preferred departure time "
                                    "(HH:MM or H:MM AM/PM): "))
            if time is not None:
                break
            print("  ! Invalid time format.")

        while True:
            flex = input("Time flexibility in minutes (0-360): ").strip()
            if flex.isdigit() and 0 <= int(flex) <= 360:
                flex = int(flex)
                break
            print("  ! Enter a whole number between 0 and 360.")

        self.requests.append({
            "name": name.title(),
            "destination": destination,
            "distance_km": distance_km,
            "distance_source": distance_source,
            "time": time,
            "flex": flex,
        })
        print(f"Request added for {name.title()}.")

    # METHOD 2: Matching Engine (greedy grouping)
    def match_requests(self):
        """Group students by destination and overlapping time windows."""
        self.cabs, self.unmatched = [], []

        by_destination = {}
        for request in self.requests:
            by_destination.setdefault(request["destination"].lower(), []).append(request)

        for key in sorted(by_destination):
            pending = sorted(by_destination[key], key=lambda request: request["time"])

            while pending:
                anchor = pending.pop(0)
                members = [anchor]
                low = anchor["time"] - anchor["flex"]
                high = anchor["time"] + anchor["flex"]
                leftover = []

                for request in pending:
                    overlaps = []
                    for day_shift in (-24 * 60, 0, 24 * 60):
                        request_low = request["time"] - request["flex"] + day_shift
                        request_high = request["time"] + request["flex"] + day_shift
                        overlap_low = max(low, request_low)
                        overlap_high = min(high, request_high)
                        if overlap_low <= overlap_high:
                            overlaps.append((overlap_low, overlap_high))

                    if len(members) < self.capacity and overlaps:
                        new_low, new_high = max(
                            overlaps, key=lambda window: window[1] - window[0]
                        )
                        members.append(request)
                        low, high = new_low, new_high
                    else:
                        leftover.append(request)
                pending = leftover

                if len(members) == 1:
                    self.unmatched.append(anchor)
                else:
                    self.cabs.append({
                        "destination": anchor["destination"],
                        "distance_km": anchor["distance_km"],
                        "distance_source": anchor.get("distance_source", "unknown"),
                        "departure": (low + high) / 2,
                        "window": (low, high),
                        "passengers": members,
                    })

        self.cabs.sort(key=lambda cab: (cab["destination"].lower(), cab["departure"]))

    # METHOD 3: Fare Calculator
    def calculate_fares(self):
        """Calculate distance-based cab fares and savings for each pooled group."""
        total_saved = 0
        for cab in self.cabs:
            passenger_count = len(cab["passengers"])
            cab["cab_fare"] = cab["distance_km"] * self.fare_per_km
            cab["per_person"] = cab["cab_fare"] / passenger_count
            cab["saved_per_person"] = cab["cab_fare"] - cab["per_person"]
            cab["saved_total"] = cab["cab_fare"] * passenger_count - cab["cab_fare"]
            total_saved += cab["saved_total"]
        return total_saved

    # METHOD 4: File Storage
    def file_storage(self, mode):
        """Save requests/results, or load requests from CSV."""
        if mode == "save":
            with open(REQUESTS_FILE, "w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow([
                    "name", "destination", "distance_km", "distance_source",
                    "time", "flexibility",
                ])
                for request in self.requests:
                    writer.writerow([
                        request["name"], request["destination"],
                        request.get("distance_km", ""),
                        request.get("distance_source", ""),
                        to_str(request["time"]), request["flex"],
                    ])

            results = {
                "capacity": self.capacity,
                "fare_per_km": self.fare_per_km,
                "origin": ORIGIN_NAME,
                "cabs": [{
                    "destination": cab["destination"],
                    "distance_km": cab["distance_km"],
                    "distance_source": cab["distance_source"],
                    "departure": to_str(cab["departure"]),
                    "passengers": [passenger["name"] for passenger in cab["passengers"]],
                    "cab_fare": round(cab["cab_fare"], 2),
                    "per_person": round(cab["per_person"], 2),
                    "saved_total": cab["saved_total"],
                } for cab in self.cabs if "per_person" in cab],
                "unmatched": [request["name"] for request in self.unmatched],
            }
            with open(RESULTS_FILE, "w", encoding="utf-8") as file:
                json.dump(results, file, indent=2)

        elif mode == "load":
            self.requests = []
            if not os.path.exists(REQUESTS_FILE):
                return
            with open(REQUESTS_FILE, newline="", encoding="utf-8") as file:
                for row in csv.DictReader(file):
                    time = to_minutes(row["time"])
                    if time is None or not row["flexibility"].isdigit():
                        print(f"Skipping invalid row: {row}")
                        continue
                    distance_text = row.get("distance_km") or ""
                    self.requests.append({
                        "name": row["name"],
                        "destination": row["destination"],
                        "distance_km": (
                            float(distance_text)
                            if distance_text.strip() else None
                        ),
                        "distance_source": row.get("distance_source", "") or "unknown",
                        "time": time,
                        "flex": int(row["flexibility"]),
                    })

    # METHOD 5: Output Display
    def display_results(self):
        """Print every cab, unmatched students, and total savings."""
        print("\n" + "=" * 58)
        print("CABPOOL RESULTS")
        print("=" * 58)

        total_saved = 0
        for index, cab in enumerate(self.cabs, 1):
            names = ", ".join(passenger["name"] for passenger in cab["passengers"])
            print(f"\nCab {index} -> {cab['destination']}")
            print(f"  Road distance : {cab['distance_km']:.1f} km "
                  f"(Rs. {self.fare_per_km}/km; {cab['distance_source']})")
            print(f"  Departure     : {to_str(cab['departure'])} "
                  f"(window {to_str(cab['window'][0])} - {to_str(cab['window'][1])})")
            print(f"  Passengers    : {names}")
            print(f"  Cab fare      : Rs. {cab['cab_fare']:.2f}")
            print(f"  Fare per head : Rs. {cab['per_person']:.2f} "
                  f"(saves Rs. {cab['saved_per_person']:.2f} each)")
            total_saved += cab["saved_total"]

        if not self.cabs:
            print("\nNo pooled cabs could be formed.")

        print("\n" + "-" * 58)
        if self.unmatched:
            print("Unmatched students:")
            for request in self.unmatched:
                print(f"  - {request['name']} -> {request['destination']} at "
                      f"{to_str(request['time'])} (+/- {request['flex']} min)")
        else:
            print("Unmatched students: none")
        print("-" * 58)
        print(f"Total savings vs. solo cabs: Rs. {total_saved:.2f}")
        print("=" * 58)


def main():
    app = CabPool(capacity=4, fare_per_km=FARE_PER_KM)
    app.file_storage("load")
    print("Welcome to CabPool!")
    print("Road distances: Nominatim geocoding and OSRM routing; "
          "map data © OpenStreetMap contributors.")
    if app.requests:
        print(f"Loaded {len(app.requests)} saved request(s).")

    while True:
        print("\n1. Add ride request\n2. View requests\n"
              "3. Match and show results\n0. Exit")
        choice = input("Choose: ").strip()

        if choice == "1":
            app.take_input()
            app.file_storage("save")
        elif choice == "2":
            if not app.requests:
                print("No requests yet.")
            for index, request in enumerate(app.requests, 1):
                distance = request.get("distance_km")
                distance_text = f"{distance:6.1f} km" if distance is not None else "distance pending"
                print(f"{index}. {request['name']:<12} {request['destination']:<24} "
                      f"{distance_text:>15}  {to_str(request['time'])}  "
                      f"+/- {request['flex']} min")
        elif choice == "3":
            if not app.requests:
                print("No requests to match.")
                continue
            app.resolve_missing_distances()
            app.match_requests()
            app.calculate_fares()
            app.file_storage("save")
            app.display_results()
        elif choice == "0":
            print("Goodbye!")
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nExiting CabPool.")
