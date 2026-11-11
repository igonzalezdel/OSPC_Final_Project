# AI USE AND REFERENCES
#
# The initial implementation of Floyd-Warshall was generated with
# ChatGPT (OpenAI, https://chatgpt.com).
#
# I used ChatGPT throughout the development process to better
# understand the algorithm and Python syntax, review the logic,
# and refine the implementation through several iterations.
# I also reviewed, edited, and tested the code, particularly
# the path reconstruction and explanatory comments.
#
# Prompts included requests to implement Floyd-Warshall with path
# reconstruction, explain the underlying logic and Python syntax,
# and review and simplify the code and comments.
#
# References:
# https://cp-algorithms.com/graph/all-pair-shortest-path-floyd-warshall.html
# https://networkx.org/documentation/stable/_modules/networkx/algorithms/shortest_paths/dense.html

from math import inf


def floyd_warshall(adjacency):
    """
    Calculate the shortest travel times between all stations.

    We start with the direct connections and check whether passing
    through other stations gives us a faster route. We also keep
    track of the next station to visit so we can recover each route.

    Input:
        adjacency: Matrix of direct travel times in minutes.
                   inf means there is no direct connection.

    Returns:
        distances: Shortest travel times between stations.
        next_station: Next station to visit on each shortest route.
    """

    # Each row represents one station, so this gives us
    # the number of stations in our network.
    n = len(adjacency)

    # We create a copy of the original adjacency matrix.
    # The original keeps the direct travel times unchanged, while
    # the copy (distances) is updated whenever we find a shorter route.
    distances = [row.copy() for row in adjacency]

    # We also want to remember how to reach each destination.
    # For now, we only know the direct connections.
    next_station = []

    for i in range(n):
        row = []

        for j in range(n):
            if i == j or adjacency[i][j] != inf:
                # We are already at j, or can travel directly to it.
                row.append(j)
            else:
                # None means we do not know a route yet.
                row.append(None)

        next_station.append(row)

    # Check whether passing through each station k gives us
    # a shorter route between any origin i and destination j.
    for k in range(n):
        for i in range(n):
            for j in range(n):

                # We cannot travel through k if either part
                # of the journey is unreachable.
                if distances[i][k] == inf or distances[k][j] == inf:
                    continue

                # Calculate the time needed to travel through k.
                # These parts may already include other stations.
                alternative = distances[i][k] + distances[k][j]

                # Update the time if we found a faster route.
                if alternative < distances[i][j]:
                    distances[i][j] = alternative

                    # Keep the first step towards k, since that
                    # is also how our new route towards j starts.
                    next_station[i][j] = next_station[i][k]

    return distances, next_station


def reconstruct_path(start, end, next_station):
    """
    Recover the stations visited along the shortest route.

    We use the next_station matrix created by Floyd-Warshall
    to follow the route until we reach the destination.

    Returns:
        A list of station indices, or None if no route exists.
    """

    # If there is no route between the two stations, return None.
    if next_station[start][end] is None:
        return None

    # Create a list to store our route, beginning with the origin.
    # current_station keeps track of where we are as we follow the route.
    path = [start]
    current_station = start

    # Keep following the route until we reach our destination.
    while current_station != end:

        # The value stored at that position is the index of the next
        # station to visit. Python numbers the stations from 0, based
        # on their order in the original adjacency matrix.
        next_stop = next_station[current_station][end]

        # Add the next station to our route.
        # append() places this value at the end of the path list.
        path.append(next_stop)

        # Our current position is now the station we just added.
        # In the next loop, we will use this new position to find
        # the following station, while the destination stays the same.
        current_station = next_stop

    # Once we reach our destination, return the complete route.
    return path


