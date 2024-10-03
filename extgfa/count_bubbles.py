"""
This script will count all the simple bubbles
I can then use this to test with and without chunking
"""
import os
import sys
import time
import pdb
import logging
import shelve
from collections import deque
from extgfa.Graph import Graph
from extgfa.ChGraph import ChGraph
from extgfa.find_bubbles import find_sb_alg

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

if len(sys.argv) < 3:
	logger.error("You need to give an input GFA and 0 for unchunked, 1 for chunked, 2 for chunked and super memory saver (more time)")
	sys.exit()

in_gfa = sys.argv[1]
g_type = int(sys.argv[2])

if g_type == 0:
	start = time.perf_counter()
	logger.info(f"Loading graph {in_gfa}")
	graph = Graph(in_gfa)
	bubbles = set()
	# find_sb_alg returns this
	# bubble = {"source":s.id, "sink":t[0].id, "inside":[n.id for n in nodes_inside]}
	# I need to mark all of them as visited or don't and find the same bubble twice
	# it will add some more time but less complexity for testing
	logger.info("finding bubbles")
	counter = 0
	for n in graph.nodes.keys():
		counter += 1
		if counter % 100_000 == 0:
			logger.info(f"Processed {counter} nodes and have found {len(bubbles)} bubbles")
		# print(n)
		for d in [0, 1]:
		# find_sb_alg takes graph, s, direction, only_simple=False, only_super=False
		# s is a node object and direction is 0 or 1
			bubble = find_sb_alg(graph, graph.nodes[n], d)
			if bubble:  # if no bubble it will return None
				if bubble['source'] > bubble['sink']:
					bubbles.add((bubble['source'], bubble['sink']))
				else:
					bubbles.add((bubble['sink'], bubble['source']))

	logger.info(f"Found {len(bubbles)} bubbles in graph {in_gfa} and it took {time.perf_counter() - start} seconds")

# elif g_type == 1:
# 	start = time.perf_counter()
# 	logger.info(f"Loading graph {in_gfa}")
# 	graph = ChGraph(in_gfa)
# 	bubbles = set()
# 	logger.info("finding bubbles")
# 	with shelve.open(graph.node_chunks) as node_chunks:
# 		for n, chunk_id in node_chunks.items():
# 			for d in [0, 1]:
# 				if n not in graph.nodes:
# 					graph.load_chunk(chunk_id)
# 				bubble = find_sb_alg(graph, graph.nodes[n], d)
# 				if bubble:  # if no bubble it will return None
# 					if bubble['source'] > bubble['sink']:
# 						bubbles.add((bubble['source'], bubble['sink']))
# 					else:
# 						bubbles.add((bubble['sink'], bubble['source']))
#
# 	logger.info(f"Found {len(bubbles)} simple bubbles in graph {in_gfa} and it took {time.perf_counter() - start} seconds")

else:
	start = time.perf_counter()
	logger.info(f"Loading graph {in_gfa}")
	bubbles = set()
	graph = ChGraph(in_gfa)

	current_chunk = 1
	# counter = set()
	bubble_counter = 0
	counter = 0
	while True:
		try:
			# logger.info(f"loading chunk {current_chunk}!!")
			graph.load_chunk(current_chunk)
		except KeyError:  # no more chunks
			break
		# logger.info("I am here")
		nodes_loop = list(graph.nodes.keys())
		logger.info(f"the chunk has {len(graph)} nodes")
		for n in nodes_loop:
			counter += 1
			if counter % 100_000 == 0:
				logger.info(f"Processed {counter} nodes and have found {len(bubbles)} bubbles")
			for d in [0, 1]:
			# find_sb_alg takes graph, s, direction, only_simple=False, only_super=False
			# s is a node object and direction is 0 or 1
				if n not in graph.nodes:
					chunk_id = graph.get_node_chunk(n)
					graph.load_chunk(chunk_id)
				bubble = find_sb_alg(graph, graph.nodes[n], d)
				if bubble:
					bubble_counter += 1

				if bubble_counter % 100 == 0:
					print(f"Found {bubble_counter} bubbles so far")
				# for c in graph.loaded_c:
				# 	counter.add(c)
				# pdb.set_trace()
				if g_type == 2:  # very low memory, always unload chunks
					if len(graph.loaded_c) > 0:
						# counter += len(graph.loaded_c)
						# not needed, unload_chunk removes the entry from loaded_c
						# try:
						# 	graph.loaded_c.remove(current_chunk)
						# except KeyError:
						# 	pass
						to_remove = list(graph.loaded_c)
						for c in to_remove:
							graph.unload_chunk(c)
						graph.loaded_c = deque()

				if bubble:  # if no bubble it will return None
					if bubble['source'] > bubble['sink']:
						bubbles.add((bubble['source'], bubble['sink']))
					else:
						bubbles.add((bubble['sink'], bubble['source']))

		if g_type == 1:  # unload loaded chunks after finishing all nodes in chunk
			to_remove = list(graph.loaded_c)
			for c in to_remove:
				graph.unload_chunk(c)
			graph.loaded_c = deque()
		logger.info(f"Finished chunk {current_chunk} and have {len(bubbles)} bubbles")
		current_chunk += 1
		# print(counter)
		# counter = 0
		graph.clear()
		# break

	logger.info(counter)
	logger.info(f"Found {len(bubbles)} bubbles in graph {in_gfa} and it took {time.perf_counter() - start} seconds")
