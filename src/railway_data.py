
# AI USE AND REFERENCES
#
# This module was developed with assistance from ChatGPT (OpenAI).
# AI assistance was used to clarify file loading, NumPy matrix
# validation, and the agreed railway data interface.
#
# The implementation was reviewed and adapted to match
# docs/interface.md.
#


import csv
import json
from pathlib import Path

import numpy as np


# --------------------------------------------------
# 1. Validate the railway network
# --------------------------------------------------

def validate_network(network):

    network = np.asarray(network, dtype=float)

    if network.ndim != 2 or network.shape[0] != network.shape[1]:
        raise ValueError("The railway network must be a square matrix.")

    if network.shape[0] == 0:
        raise ValueError("The railway network cannot be empty.")

    if np.isnan(network).any() or (network < 0).any():
        raise ValueError("Travel times cannot contain NaN or negative values.")

    if not np.allclose(network, network.T):
        raise ValueError("The railway network must be symmetric.")

    if not np.all(np.diag(network) == 0):
        raise ValueError("The diagonal of the network must contain zeros.")

    return network


# --------------------------------------------------
# 2. Validate passenger demand
# --------------------------------------------------

def validate_demand(demand):

    demand = np.asarray(demand)

    if demand.ndim != 2 or demand.shape[0] != demand.shape[1]:
        raise ValueError("The demand matrix must be square.")

    if demand.shape[0] == 0:
        raise ValueError("The demand matrix cannot be empty.")

    if not np.isfinite(demand).all():
        raise ValueError("Passenger demand must contain finite values.")

    if (demand < 0).any():
        raise ValueError("Passenger demand cannot be negative.")

    if not np.equal(demand, np.floor(demand)).all():
        raise ValueError("Passenger demand must contain integer values.")

    if not np.all(np.diag(demand) == 0):
        raise ValueError("The diagonal of the demand matrix must contain zeros.")

    return demand.astype(int)


# --------------------------------------------------
# 3. Load station names and their order
# --------------------------------------------------

def load_station_names(file_path):

    station_names = []
    station_ids = []

    with open(file_path, "r", newline="", encoding="utf-8") as file:

        reader = csv.DictReader(file)

        for row in reader:
            station_ids.append(int(row["station_id"]))
            station_names.append(row["station_name"].strip())

    if not station_names:
        raise ValueError("The station list cannot be empty.")

    if station_ids != list(range(len(station_names))):
        raise ValueError("Station IDs must follow the order 0 to n-1.")

    if any(not name for name in station_names):
        raise ValueError("Station names cannot be empty.")

    return station_names


# --------------------------------------------------
# 4. Load a complete railway dataset
# --------------------------------------------------

def load_railway_data(dataset_path):

    dataset_path = Path(dataset_path)

    # These filenames are part of our reusable data format.
    station_file = dataset_path / "stations.csv"
    network_file = dataset_path / "network.csv"
    demand_file = dataset_path / "demand.csv"
    metadata_file = dataset_path / "metadata.json"

    # Check that all required files exist.
    required_files = [
        station_file,
        network_file,
        demand_file,
        metadata_file
    ]

    for file_path in required_files:
        if not file_path.exists():
            raise FileNotFoundError(
                f"Required dataset file not found: {file_path}"
            )

    # Load the station names in their agreed order.
    station_names = load_station_names(station_file)

    # Load the numerical matrices.
    network = np.loadtxt(
        network_file,
        delimiter=",",
        dtype=float,
        ndmin=2
    )

    demand = np.loadtxt(
        demand_file,
        delimiter=",",
        dtype=float,
        ndmin=2
    )

    # Apply the permanent validation functions.
    network = validate_network(network)
    demand = validate_demand(demand)

    # All three inputs must use the same station order.
    number_of_stations = len(station_names)

    if network.shape != (number_of_stations, number_of_stations):
        raise ValueError("Network dimensions do not match the station list.")

    if demand.shape != (number_of_stations, number_of_stations):
        raise ValueError("Demand dimensions do not match the station list.")

    # Load the dataset description and provenance.
    with open(metadata_file, "r", encoding="utf-8") as file:
        metadata = json.load(file)

    return {
        "station_names": station_names,
        "network": network,
        "demand": demand,
        "metadata": metadata
    }


# --------------------------------------------------
# 5. Display dataset information
# --------------------------------------------------

def get_dataset_info(data):

    metadata = data["metadata"]

    return {
        "dataset_name": metadata.get("dataset_name", "Unknown"),
        "description": metadata.get("description", "Not provided"),
        "source": metadata.get("source", "Not provided"),
        "provisional": metadata.get("provisional", True),
        "number_of_stations": len(data["station_names"]),
        "network_shape": data["network"].shape,
        "demand_shape": data["demand"].shape,
        "travel_time_unit": metadata.get("travel_time_unit", "minutes"),
        "demand_unit": metadata.get("demand_unit", "trips per day")
    }

