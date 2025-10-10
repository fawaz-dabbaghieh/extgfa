import datetime
import sys

from GFASubgraph.Graph import Graph

if len(sys.argv) < 3:
	print("You need to give the GFA file and a node as input")
	sys.exit()

in_gfa  = sys.argv[1]
node_id = sys.argv[2]

print(f"loading the graph now {datetime.datetime.now()}")
graph = Graph(in_gfa, low_mem=True)
print(f"finished loading the graph now {datetime.datetime.now()}")

print(f"The neighbors of Node {node_id} are {graph.nodes[node_id].neighbors()}")