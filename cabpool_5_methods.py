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

REQUESTS_FILE = "requests.csv"
RESULTS_FILE = "results.json"


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
    minutes = max(0, min(int(round(minutes)), 24 * 60 - 1))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


class CabPool:
    def __init__(self, capacity=4, cab_fare=600):
        self.capacity = capacity
        self.cab_fare = cab_fare
        self.requests = []
        self.cabs = []
        self.unmatched = []

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
            destination = " ".join(input("Destination: ").split())
            if len(destination) >= 2:
                break
            print("  ! Enter a valid destination.")

        while True:
            time = to_minutes(input("Preferred departure time "
                                    "(HH:MM or H:MM AM/PM): "))
            if time is not None:
                break
            print("  ! Invalid time format.")

        while True:
            flex = input("Time flexibility in minutes (0-180): ").strip()
            if flex.isdigit() and 0 <= int(flex) <= 180:
                flex = int(flex)
                break
            print("  ! Enter a whole number between 0 and 180.")

        self.requests.append({
            "name": name.title(),
            "destination": destination.title(),
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
                    new_low = max(low, request["time"] - request["flex"])
                    new_high = min(high, request["time"] + request["flex"])
                    if len(members) < self.capacity and new_low <= new_high:
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
                        "departure": (low + high) / 2,
                        "window": (low, high),
                        "passengers": members,
                    })

        self.cabs.sort(key=lambda cab: (cab["destination"].lower(), cab["departure"]))

    # METHOD 3: Fare Calculator
    def calculate_fares(self):
        """Add per-person fare and savings to every cab. Returns total savings."""
        total_saved = 0
        for cab in self.cabs:
            passenger_count = len(cab["passengers"])
            cab["per_person"] = self.cab_fare / passenger_count
            cab["saved_per_person"] = self.cab_fare - cab["per_person"]
            cab["saved_total"] = self.cab_fare * passenger_count - self.cab_fare
            total_saved += cab["saved_total"]
        return total_saved

    # METHOD 4: File Storage
    def file_storage(self, mode):
        """Save requests/results, or load requests from CSV."""
        if mode == "save":
            with open(REQUESTS_FILE, "w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["name", "destination", "time", "flexibility"])
                for request in self.requests:
                    writer.writerow([request["name"], request["destination"],
                                     to_str(request["time"]), request["flex"]])

            results = {
                "capacity": self.capacity,
                "cab_fare": self.cab_fare,
                "cabs": [{
                    "destination": cab["destination"],
                    "departure": to_str(cab["departure"]),
                    "passengers": [passenger["name"] for passenger in cab["passengers"]],
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
                    self.requests.append({
                        "name": row["name"],
                        "destination": row["destination"],
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
            print(f"  Departure     : {to_str(cab['departure'])} "
                  f"(window {to_str(cab['window'][0])} - {to_str(cab['window'][1])})")
            print(f"  Passengers    : {names}")
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
    app = CabPool(capacity=4, cab_fare=600)
    app.file_storage("load")
    print("Welcome to CabPool!")
    if app.requests:
        print(f"Loaded {len(app.requests)} saved request(s).")

    while True:
        print("\n1. Add ride request\n2. View requests\n"
              "3. Match and show results\n4. Load sample data\n0. Exit")
        choice = input("Choose: ").strip()

        if choice == "1":
            app.take_input()
            app.file_storage("save")
        elif choice == "2":
            if not app.requests:
                print("No requests yet.")
            for index, request in enumerate(app.requests, 1):
                print(f"{index}. {request['name']:<12} {request['destination']:<24} "
                      f"{to_str(request['time'])}  +/- {request['flex']} min")
        elif choice == "3":
            if not app.requests:
                print("No requests to match.")
                continue
            app.match_requests()
            app.calculate_fares()
            app.file_storage("save")
            app.display_results()
        elif choice == "4":
            sample = [
                ("Aman", "New Delhi Station", "18:00", 30),
                ("Riya", "New Delhi Station", "18:15", 20),
                ("Karan", "New Delhi Station", "17:50", 30),
                ("Sneha", "New Delhi Station", "18:30", 15),
                ("Neha", "IGI Airport", "05:00", 30),
                ("Arjun", "IGI Airport", "05:20", 30),
                ("Pooja", "IGI Airport", "09:00", 15),
            ]
            for name, destination, time, flexibility in sample:
                app.requests.append({
                    "name": name,
                    "destination": destination,
                    "time": to_minutes(time),
                    "flex": flexibility,
                })
            app.file_storage("save")
            print("Sample data loaded.")
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
