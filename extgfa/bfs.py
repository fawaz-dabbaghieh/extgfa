import logging
from collections import deque


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

def main_while_loop(graph, start_node, queue, visited, n_size):
    neighborhood = {start_node}
    counter = 0
    while len(queue) > 0 and len(neighborhood) <= n_size:
        counter += 1
        if counter % 100 == 0:
            logging.info(f"BFS neighborhood is of length {len(neighborhood)}")
        start = queue.popleft()

        if start not in neighborhood:
            neighborhood.add(start)

        visited.add(start)

        neighbors = graph.neighbors(start)

        for n in neighbors:
            if n not in visited and n not in queue:
                queue.append(n)

    return neighborhood


def bfs(graph, start_node, n_size):
    """
    Runs bfs and returns the neighborhood smaller than size
    Using only bfs was resulting in a one-sided neighborhood.
    So the neighborhood I was getting was mainly going from the start node
    into one direction because we have FIFO and it basically keeps going
    in that direction.
    :param graph: A graph object from class Graph
    :param start_node: starting node for the BFS search
    :param size: size of the neighborhood to return
    """
    queue = deque()
    visited = set()
    queue.append(start_node)
    visited.add(start_node)

    # lonely node
    if len(graph.neighbors(start_node)) == 0:
        return {start_node}

    neighborhood = main_while_loop(graph, start_node, queue, visited, n_size)
    return neighborhood
