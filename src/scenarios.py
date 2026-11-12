
# AI USE AND REFERENCES
#
# The initial design and implementation of this scenario generator
# were developed with assistance from ChatGPT (OpenAI).
# AI assistance was used to clarify NumPy random generators,
# reproducible random seeds, and the modification of railway matrices.
# The implementation was reviewed and adapted to match the agreed
# project interface in docs/interface.md.


import numpy as np

#This defaults are our proposed simulation assumptions
#We keep them as parameters so we can change the model, if needed
#without rewriting the algorithm

def generate_disruption_scenarios(
    network,
    num_scenarios=100,
    seed=42,
    min_disruptions=1,
    max_disruptions=3,
    block_probability=0.5,
    min_delay=5,
    max_delay=30
):
    # --------------------------------------------------
    # 1. Validate the original railway network
    # --------------------------------------------------

    network = np.array(network, dtype=float, copy=True)

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

    # --------------------------------------------------
    # 2. Identify available railway links
    # --------------------------------------------------

    # The upper triangle excludes the diagonal and avoids duplicate directions.

    available_links = np.argwhere(
        np.triu(np.isfinite(network), k=1)
    )

    if len(available_links) == 0:
        raise ValueError("The network has no available railway links.")

    # --------------------------------------------------
    # 3. Validate simulation parameters
    # --------------------------------------------------

    if num_scenarios < 1:
        raise ValueError("The number of scenarios must be at least 1.")

    if min_disruptions < 1 or min_disruptions > max_disruptions:
        raise ValueError("The disruption range is invalid.")

    if max_disruptions > len(available_links):
        raise ValueError("There are not enough available links.")

    if not 0 <= block_probability <= 1:
        raise ValueError("Block probability must be between 0 and 1.")

    if min_delay < 1 or min_delay > max_delay:
        raise ValueError("The delay range is invalid.")

    if not isinstance(num_scenarios, (int, np.integer)) or isinstance(num_scenarios, (bool, np.bool_)):
        raise ValueError("The number of scenarios must be an integer.")

    if not isinstance(min_disruptions, (int, np.integer)) or not isinstance(max_disruptions, (int, np.integer)):
        raise ValueError("The number of disruptions must be integers.")

    # --------------------------------------------------
    # 4. Create reproducible random generators
    # --------------------------------------------------

    # This makes results independent of the number of MPI workers.

    seeds = np.random.SeedSequence(seed).spawn(num_scenarios)

    # --------------------------------------------------
    # 5. Initialize result lists
    # --------------------------------------------------

    scenarios = []
    scenario_records = []

    # --------------------------------------------------
    # 6. Generate each disruption scenario
    # --------------------------------------------------

    # This prevents disruptions from carrying over between scenarios.

    for scenario_number, scenario_seed in enumerate(seeds):

        rng = np.random.default_rng(scenario_seed)

        scenario_matrix = network.copy()

        num_disruptions = rng.integers(
            min_disruptions,
            max_disruptions + 1
        )

        selected_indices = rng.choice(
            len(available_links),
            size=num_disruptions,
            replace=False
        )

        disruptions = []

        # --------------------------------------------------
        # 7. Apply blocking or delays to selected links
        # --------------------------------------------------

        for selected_index in selected_indices:

            i, j = available_links[selected_index]

            if rng.random() < block_probability:

                scenario_matrix[i, j] = np.inf
                scenario_matrix[j, i] = np.inf

                disruption = {
                    "link": (int(i), int(j)),
                    "type": "blocked"
                }

            else:

                delay = int(rng.integers(min_delay, max_delay + 1))

                scenario_matrix[i, j] += delay
                scenario_matrix[j, i] += delay

                disruption = {
                    "link": (int(i), int(j)),
                    "type": "delayed",
                    "delay_minutes": delay
                }

            disruptions.append(disruption)

        # --------------------------------------------------
        # 8. Store the generated scenario and its records
        # --------------------------------------------------

        scenarios.append(scenario_matrix)

        scenario_records.append({
            "scenario": scenario_number,
            "disruptions": disruptions
        })


    # --------------------------------------------------
    # 9. Convert and return the results
    # --------------------------------------------------

    # The expected shape is (scenarios, stations, stations).

    scenarios = np.array(scenarios, dtype=float)

    return scenarios, scenario_records
