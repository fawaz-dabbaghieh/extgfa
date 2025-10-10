from extgfa.Graph import Graph
from extgfa.ChGraph import ChGraph
import time
import sys
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')


if len(sys.argv) < 6:
	logger.error("You need to give input graph, start node, type (0, 1) for unchunked, chunked, size of neighborhood "
				 "around the start node, and limit on how many chunks to keep in memory before unloading")
	sys.exit()

in_gfa = sys.argv[1]
start_node = sys.argv[2]
graph_type = int(sys.argv[3])
size = int(sys.argv[4])
limit = int(sys.argv[5])


start = time.perf_counter()
if graph_type == 0:
	logger.info(f"Loading graph from {in_gfa}")
	graph = Graph(in_gfa)
elif graph_type == 1:
	graph = ChGraph(in_gfa)
	graph.loaded_c_limit = limit
else:
	logger.error("Graph type not supported")
	sys.exit()

logger.info(f"Finding BFS neighborhood of size {size}")
x = graph.bfs(start_node, size)
logger.info(f"It took {time.perf_counter() - start} to retrieve a neighborhood of size {len(x)}")
