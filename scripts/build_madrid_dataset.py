
# AI USE AND REFERENCES
#
# This script was developed with assistance from Claude (Anthropic).
# AI assistance was used to find the Renfe open datasets, parse the
# GTFS timetable format and write the gravity model calibration.
# The code was reviewed, run and checked against docs/interface.md
# and src/railway_data.py.
#
# Prompts included requests to find real Cercanias Madrid ridership
# data, build a station network from GTFS stop_times, and estimate an
# origin-destination matrix from boardings and alightings per station.
#
# Data sources (both CC BY 4.0, published by Renfe on datos.gob.es):
# - Cercanias GTFS timetables:
#   https://datos.gob.es/es/catalogo/ea0003337-horarios-cercanias1
#   download: https://ssl.renfe.com/ftransit/Fichero_CER_FOMENTO/fomento_transit.zip
# - Passengers per station and 30-minute slot, Madrid, 2018:
#   https://datos.gob.es/es/catalogo/ea0003337-volumen-de-viajeros-por-franja-horaria-madrid1
#
# Method references:
# - Doubly constrained gravity model and Furness/IPF balancing:
#   Ortuzar & Willumsen, Modelling Transport, ch. 5.

"""
Build the Madrid Cercanias dataset in the format read by
src/railway_data.py (see docs/interface.md).

Usage (from the repository root):
    python scripts/build_madrid_dataset.py --gtfs path/to/fomento_transit

The GTFS folder is the unzipped fomento_transit.zip (not committed,
because stop_times.txt is 270 MB). The ridership file is committed in
data/raw/.

Output folder data/madrid_cercanias/:
    stations.csv      station_id (0..n-1), station_name, renfe_code, lat, lon,
                      boardings_per_day, alightings_per_day
    network.csv       n x n travel times in minutes, inf = no direct link
    demand.csv        n x n passenger trips per day (integers)
    demand_peak.csv   same, only 07:00-09:30
    demand_offpeak.csv same, rest of the day
    metadata.json     sources, parameters and summary numbers
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse.csgraph import floyd_warshall


# Madrid lines in the Renfe GTFS have route ids starting with "10T"
MADRID_ROUTE_PREFIX = "10T"

# Vallecas has code 70001 in the 2018 ridership file and 70005 in the GTFS
CODE_FIX = {"70001": "70005"}

PEAK_SLOTS = ["07:00 - 07:30", "07:30 - 08:00", "08:00 - 08:30",
              "08:30 - 09:00", "09:00 - 09:30"]


# --------------------------------------------------
# 1. Read the GTFS timetable
# --------------------------------------------------

def clean(df):
    # Renfe pads columns and values with spaces
    df.columns = df.columns.str.strip()
    return df.apply(lambda col: col.str.strip())


def to_minutes(times):
    # "HH:MM:SS" -> minutes after midnight (HH can be 24 or more)
    parts = times.str.strip().str.split(":", expand=True).astype(int)
    return parts[0] * 60 + parts[1] + parts[2] / 60


def load_gtfs(gtfs_path, service_date):
    routes = clean(pd.read_csv(gtfs_path / "routes.txt", dtype=str))
    trips = clean(pd.read_csv(gtfs_path / "trips.txt", dtype=str))
    calendar = clean(pd.read_csv(gtfs_path / "calendar.txt", dtype=str))
    stops = clean(pd.read_csv(gtfs_path / "stops.txt", dtype=str))

    madrid_routes = routes[routes.route_id.str.startswith(MADRID_ROUTE_PREFIX)]

    # Keep only the services that run on the chosen day
    weekday = ["monday", "tuesday", "wednesday", "thursday",
               "friday", "saturday", "sunday"][pd.Timestamp(service_date).dayofweek]
    active = calendar[(calendar.start_date <= service_date)
                      & (calendar.end_date >= service_date)
                      & (calendar[weekday] == "1")]

    madrid_trips = trips[trips.route_id.isin(madrid_routes.route_id)
                         & trips.service_id.isin(active.service_id)]

    wanted = {"trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"}
    stop_times = pd.read_csv(gtfs_path / "stop_times.txt", dtype=str,
                             usecols=lambda c: c.strip() in wanted)
    stop_times.columns = stop_times.columns.str.strip()
    stop_times["trip_id"] = stop_times.trip_id.str.strip()
    stop_times = stop_times[stop_times.trip_id.isin(set(madrid_trips.trip_id))].copy()
    stop_times["stop_id"] = stop_times.stop_id.str.strip()
    stop_times["seq"] = stop_times.stop_sequence.astype(int)
    stop_times["arr"] = to_minutes(stop_times.arrival_time)
    stop_times["dep"] = to_minutes(stop_times.departure_time)

    return stops, madrid_trips, stop_times.sort_values(["trip_id", "seq"])


# --------------------------------------------------
# 2. Build the links between the kept stations
# --------------------------------------------------

def build_links(stop_times, keep, min_trips=2):
    # Two kept stations that come one after the other on a trip are linked.
    # Stations we drop are skipped, so the lines stay connected.
    s = stop_times[stop_times.stop_id.isin(keep)].copy()
    s["next_stop"] = s.groupby("trip_id").stop_id.shift(-1)
    s["next_arr"] = s.groupby("trip_id").arr.shift(-1)
    s = s.dropna(subset=["next_stop"])
    s["minutes"] = s.next_arr - s.dep
    s = s[(s.minutes > 0) & (s.stop_id != s.next_stop)]

    # One link per pair of stations, both directions together
    s["a"] = s[["stop_id", "next_stop"]].min(axis=1)
    s["b"] = s[["stop_id", "next_stop"]].max(axis=1)
    links = (s.groupby(["a", "b"]).minutes
               .agg(minutes="median", trips="size").reset_index())

    # Links seen in only one train that day are unusual routings
    return links[links.trips >= min_trips].reset_index(drop=True)


# --------------------------------------------------
# 3. Estimate trips between stations (gravity model)
# --------------------------------------------------

def gravity_model(boardings, alightings, travel_times, beta, max_iter=10_000):
    # trips[i, j] = a_i * boardings_i * b_j * alightings_j * exp(-beta * time_ij)
    # a and b are found by IPF so that every row adds up to the real
    # boardings and every column to the real alightings.
    deterrence = np.exp(-beta * travel_times)
    deterrence[~np.isfinite(travel_times)] = 0.0
    np.fill_diagonal(deterrence, 0.0)

    trips = np.outer(boardings, alightings) * deterrence
    for _ in range(max_iter):
        trips *= (boardings / trips.sum(axis=1))[:, None]
        trips *= (alightings / trips.sum(axis=0))[None, :]
        if (np.allclose(trips.sum(axis=1), boardings, rtol=1e-9)
                and np.allclose(trips.sum(axis=0), alightings, rtol=1e-9)):
            break
    return trips


def demand_matrix(table, keep_ids, travel_times, beta):
    boardings = table.loc[keep_ids, "VIAJEROS_SUBIDOS"].to_numpy(float)
    alightings = table.loc[keep_ids, "VIAJEROS_BAJADOS"].to_numpy(float)
    # Inside the kept stations totals can differ a bit, so we match them
    alightings *= boardings.sum() / alightings.sum()
    trips = gravity_model(boardings, alightings, travel_times, beta)
    return np.rint(trips).astype(int)


# --------------------------------------------------
# 4. Main
# --------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gtfs", required=True, type=Path)
    parser.add_argument("--ridership", type=Path,
                        default=Path("data/raw/renfe_viajeros_madrid_2018.csv"))
    parser.add_argument("--out", type=Path, default=Path("data/madrid_cercanias"))
    parser.add_argument("--n", type=int, default=60, help="keep the n busiest stations")
    parser.add_argument("--date", default="20261111", help="weekday used for the timetable")
    parser.add_argument("--beta", type=float, default=0.05,
                        help="how fast demand falls with travel time (per minute)")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    # Ridership per station: whole day, peak and off-peak
    ridership = pd.read_csv(args.ridership, sep=";")
    ridership["stop_id"] = (ridership.CODIGO_ESTACION.astype(str)
                            .str.zfill(5).replace(CODE_FIX))
    columns = ["VIAJEROS_SUBIDOS", "VIAJEROS_BAJADOS"]
    day = ridership.groupby("stop_id")[columns].sum()
    peak = (ridership[ridership.TRAMO_HORARIO.isin(PEAK_SLOTS)]
            .groupby("stop_id")[columns].sum().reindex(day.index, fill_value=0))
    offpeak = day - peak

    # Timetable
    stops, trips, stop_times = load_gtfs(args.gtfs, args.date)
    in_gtfs = day.index[day.index.isin(set(stop_times.stop_id))]
    missing = sorted(set(day.index) - set(in_gtfs))

    # Keep the n busiest stations; station 0 is the busiest
    keep_ids = (day.loc[in_gtfs].sort_values("VIAJEROS_SUBIDOS", ascending=False)
                .head(args.n).index)
    index = {code: i for i, code in enumerate(keep_ids)}
    n = len(keep_ids)

    links = build_links(stop_times, set(keep_ids))
    network = np.full((n, n), np.inf)
    np.fill_diagonal(network, 0.0)
    for link in links.itertuples():
        i, j = index[link.a], index[link.b]
        network[i, j] = network[j, i] = round(float(link.minutes), 1)

    # Shortest times on the normal network, used by the gravity model
    shortest = floyd_warshall(np.where(np.isinf(network), 0, network), directed=False)
    if np.isinf(shortest).any():
        raise ValueError("Some stations cannot be reached; increase --n or check links.")

    demand = {
        "demand": demand_matrix(day, keep_ids, shortest, args.beta),
        "demand_peak": demand_matrix(peak, keep_ids, shortest, args.beta),
        "demand_offpeak": demand_matrix(offpeak, keep_ids, shortest, args.beta),
    }

    # Station list in the format of src/railway_data.py
    names = stops.drop_duplicates("stop_id").set_index("stop_id")
    stations = pd.DataFrame({
        "station_id": range(n),
        "station_name": [names.loc[c, "stop_name"] for c in keep_ids],
        "renfe_code": list(keep_ids),
        "lat": [float(names.loc[c, "stop_lat"]) for c in keep_ids],
        "lon": [float(names.loc[c, "stop_lon"]) for c in keep_ids],
        "boardings_per_day": day.loc[keep_ids, "VIAJEROS_SUBIDOS"].to_numpy(),
        "alightings_per_day": day.loc[keep_ids, "VIAJEROS_BAJADOS"].to_numpy(),
    })

    stations.to_csv(args.out / "stations.csv", index=False)
    np.savetxt(args.out / "network.csv", network, delimiter=",", fmt="%.1f")
    for name, matrix in demand.items():
        np.savetxt(args.out / f"{name}.csv", matrix, delimiter=",", fmt="%d")

    finite = ~np.eye(n, dtype=bool)
    metadata = {
        "dataset_name": "Madrid Cercanias, 60 busiest stations",
        "description": ("Real Cercanias Madrid network (GTFS timetable) with "
                        "origin-destination demand estimated from real "
                        "boardings and alightings per station."),
        "source": ("Renfe Cercanias GTFS (fomento_transit.zip) and Renfe "
                   "'Volumen de viajeros por franja horaria (Madrid)' 2018, "
                   "CC BY 4.0, datos.gob.es"),
        "provisional": False,
        "travel_time_unit": "minutes",
        "demand_unit": "trips per day",
        "timetable_date": args.date,
        "ridership_year": 2018,
        "number_of_stations": n,
        "share_of_daily_boardings_covered": round(
            float(day.loc[keep_ids, "VIAJEROS_SUBIDOS"].sum()
                  / day["VIAJEROS_SUBIDOS"].sum()), 4),
        "number_of_links": int(len(links)),
        "madrid_trains_on_timetable_date": int(len(trips)),
        "gravity_beta_per_minute": args.beta,
        "peak_slots": "07:00-09:30",
        "daily_trips_in_demand": int(demand["demand"].sum()),
        "average_trip_minutes": round(float(
            (demand["demand"] * np.where(finite, shortest, 0)).sum()
            / demand["demand"].sum()), 1),
        "ridership_stations_missing_in_gtfs": missing,
        "station_code_fixes": CODE_FIX,
        "limitations": [
            "Ridership is from 2018 (pre-COVID).",
            "Demand between stations is estimated with a gravity model, not observed.",
            "beta is an assumption; test other values for sensitivity.",
            "Changing lines costs 0 minutes (no transfer penalty).",
            "Travel time of a link is the median over both directions and all trains that day.",
        ],
    }
    (args.out / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: metadata[k] for k in
                      ["number_of_stations", "number_of_links",
                       "share_of_daily_boardings_covered",
                       "daily_trips_in_demand", "average_trip_minutes"]}, indent=2))


if __name__ == "__main__":
    main()
