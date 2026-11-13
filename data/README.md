# Data

## madrid_cercanias/ (main dataset)

Real Cercanías Madrid network with the 60 busiest stations (94.1% of daily boardings).
Load it with `src/railway_data.load_railway_data("data/madrid_cercanias")`.

| File | Content |
|---|---|
| `stations.csv` | `station_id` 0..59 (0 = busiest), name, Renfe code, lat/lon, real boardings/alightings per day |
| `network.csv` | 60 x 60 travel times in minutes, `inf` = no direct link, symmetric, 63 links |
| `demand.csv` | 60 x 60 trips per day (853,902 in total) |
| `demand_peak.csv` / `demand_offpeak.csv` | same for 07:00-09:30 and the rest of the day |
| `metadata.json` | sources, parameters, limitations |
| `network_map.png` | map of the network |

Rebuild: download and unzip
https://ssl.renfe.com/ftransit/Fichero_CER_FOMENTO/fomento_transit.zip, then

    python scripts/build_madrid_dataset.py --gtfs path/to/fomento_transit

How it is built:
- Links: two kept stations that follow each other on a train of the timetable day.
  Dropped stations in between are skipped, so the lines stay connected. Travel time
  is the median over both directions and all trains. Links seen in fewer than 2 trains are dropped.
- Demand: doubly constrained gravity model, `T_ij ∝ O_i D_j exp(-0.05 t_ij)`, balanced with
  IPF so each station's row and column match Renfe's real boardings and alightings.

Limitations: 2018 ridership (pre-COVID), estimated (not observed) origin-destination demand,
`beta = 0.05` is an assumption, no transfer penalty, Vallecas code fixed 70001 -> 70005.

Timing hint: one sequential Floyd-Warshall on this network takes ~0.011 s on a laptop,
so the 10-minute sequential baseline needs roughly 50,000 scenarios (check on the cluster).

## raw/
`renfe_viajeros_madrid_2018.csv`: Renfe, passengers per station per 30-minute slot, Madrid 2018 (CC BY 4.0).
The GTFS zip is not committed (270 MB unzipped).
