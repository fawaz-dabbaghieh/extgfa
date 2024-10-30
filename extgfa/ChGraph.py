import sys
import os
import pickle
import pdb
import logging
import shelve
import pickle
from collections import deque
from extgfa.bfs import bfs


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')


class Node:
	def __init__(self, identifier):
		self.id = identifier  # size is between 28 and 32 bytes
		self.seq = ""
		self.start = set()  # 96 bytes for 4 neighbors
		self.end = set()  # 96 bytes
		self.visited = False  # 28 bytes (used for bubble and superbubble detection)
		self.chunk_id = -1
		self.tags = dict()
		self.optional_info = []

	def __len__(self):
		return len(self.seq)

	def to_gfa_line(self, with_seq=True):
		"""
		returns the GFA S line for the node
		"""
		if with_seq:  # in case with_seq was true but there was no seq
			if self.seq == "":
				seq = "*"
			else:
				seq = self.seq
		else:
			seq = "*"
		tags = []
		for tag_id, tag in self.tags.items():
			tags.append(f"{tag_id}:{tag[0]}:{tag[1]}")
		tags.append(f"cid:i:{self.chunk_id}")
		return "\t".join(["S", self.id, seq] + tags)


class ChGraph:
	"""
	Graph object containing the important information about the graph
	"""

	def __init__(self, graph_file):
		# check for index and db
		if not graph_file.endswith(".gfa"):
			print("the graph needs to end with .gfa")
			sys.exit(1)

		if not os.path.exists(graph_file):
			print(f"graph file {graph_file} does not exist")
			sys.exit(1)

		if not os.path.exists(graph_file[:-4] + ".db"):
			logger.error(f"Could not find DB associated with {graph_file}\nMake sure this is the chunked graph")
			sys.exit(1)

		if not os.path.exists(graph_file[:-4] + ".index"):
			logger.error(f"Could not find the offsets index associated with {graph_file}\nMake sure this is the chunked graph")
			sys.exit(1)

		with open(graph_file[:-4] + ".index", "rb") as f:
			self.offsets = pickle.load(f)

		self.node_chunks = graph_file[:-4] + ".db"

		self.nodes = dict()
		self.graph_name = graph_file

		self.loaded_c = deque() # newly loaded chunk IDs
		self.loaded_c_limit = 10

	def __len__(self):
		"""
		overloading the length function
		"""
		return len(self.nodes)

	def __str__(self):
		"""
		overloading the string function for printing
		"""
		total_len = sum([len(x) for x in self.nodes.values()])
		return f"The graph has {len(self.nodes)} nodes, and total seq length of {total_len}"


	def __contains__(self, key):
		"""
        overloading the in operator to check if node exists in graph
        """
		return key in self.nodes

	def __getitem__(self, key):
		"""
        overloading the bracket operator
        """
		try:
			return self.nodes[key]
		except KeyError:
			chunk_id = self.get_node_chunk(key)
			if chunk_id is None:
				return None
			self.load_chunk(chunk_id)
			return self.nodes[key]

	def total_seq_length(self):
		"""
		returns total sequence length
		"""
		total = 0
		for n in self.nodes.values():
			total += n.seq_len
		return total

	def reset_visited(self):
		"""
		resets all nodes.visited to false
		"""
		for n in self.nodes.values():
			n.visited = False

	def clear(self):
		"""
		removes all nodes from the graph
		"""
		del self.nodes
		self.nodes = dict()
		self.loaded_c = deque()

	def get_node_chunk(self, node_id):
		"""
		returns the chunk id of the node using the database available
		"""
		if node_id in self.nodes:
			return self.nodes[node_id].tags['cid']
		else:
			with shelve.open(self.node_chunks) as node_chunk:
			# node_chunk = shelve.open(self.node_chunks)
				try:
					chunk_id = node_chunk[node_id]
				except KeyError:
					return None
				# node_chunk.close()
				return chunk_id

	def neighbors(self, node_id):
		"""
		returns all connected nodes to node_id, loads chunks if required
		"""
		neighbors = []
		# node_chunk = shelve.open(self.node_chunks)
		try:  # if not loaded, it will through KeyError
			# self.nodes[node_id]
			return [x[0] for x in self.nodes[node_id].start] + [x[0] for x in self.nodes[node_id].end]
		except KeyError:
			with shelve.open(self.node_chunks) as node_chunk:
				try:
					new_chunk = node_chunk[node_id]
				except KeyError:  # node somehow not in database (means bug)
					logger.error(f"Something went wrong as node {node_id} does not exist in the DB")
					logger.error(f"Please make sure you are using the correct graph and nothing has been edited")
					sys.exit()
				logger.info(f"node {node_id} is not in the graph, loading chunk {new_chunk}")
				self.load_chunk(new_chunk)
				return [x[0] for x in self.nodes[node_id].start] + [x[0] for x in self.nodes[node_id].end]
		
	def children(self, node_id, direction):
		"""
		returns the children of a node in given direction
		"""
		# node_chunk = shelve.open(self.node_chunks)
		with shelve.open(self.node_chunks) as node_chunk:
			if node_id not in self.nodes:  # need to load a chunk
				# this should never happen
				new_chunk = node_chunk[node_id]
				# new_chunk = int(node_id.split("_")[-1])
				self.load_chunk(new_chunk)
				# self.loaded_c.append(new_chunk)

			if direction == 0:
				for nn in self.nodes[node_id].start:
					if nn[0] not in self.nodes:  # need to load a chunk
						# I need to load a new chunk
						# pdb.set_trace()
						new_chunk = node_chunk[nn[0]]
						# new_chunk = int(nn[0].split("_")[-1])
						self.load_chunk(new_chunk)
						# self.loaded_c.append(new_chunk)
				# node_chunk.close()
				return [(x[0], x[1]) for x in self.nodes[node_id].start]
				# return [x[0] for x in self.nodes[node_id].start]
			elif direction == 1:
				for nn in self.nodes[node_id].end:
					if nn[0] not in self.nodes:
						# pdb.set_trace()digitalizing
						new_chunk = node_chunk[nn[0]]
						# new_chunk = int(nn[0].split("_")[-1])
						self.load_chunk(new_chunk)
						# self.loaded_c.append(new_chunk)
				# node_chunk.close()
				return [(x[0], x[1]) for x in self.nodes[node_id].end]
				# return [x[0] for x in self.nodes[node_id].end]
			else:
				# node_chunk.close()
				raise Exception("Trying to access a wrong direction in node {}".format(self.id))

	def remove_node(self, n_id):
		"""
		remove a node and its corresponding edges
		"""
		starts = [x for x in self.nodes[n_id].start]
		for n_start in starts:
			overlap = n_start[2]
			if n_start[1] == 1:
				self.nodes[n_start[0]].end.remove((n_id, 0, overlap))
			else:
				self.nodes[n_start[0]].start.remove((n_id, 0, overlap))

		ends = [x for x in self.nodes[n_id].end]
		for n_end in ends:
			overlap = n_end[2]
			if n_end[1] == 1:
				self.nodes[n_end[0]].end.remove((n_id, 1, overlap))
			else:
				self.nodes[n_end[0]].start.remove((n_id, 1, overlap))

		del self.nodes[n_id]


	def write_graph(self, set_of_nodes=None,
					output_file="output_graph.gfa",
					append=False, optional_info=True):
		"""writes a graph file as GFA
		list_of_nodes can be a list of node ids to write
		ignore_nodes is a list of node ids to not write out
		if append is set to true then output file should be an existing
		graph file to append to
		modified to output a modified graph file
		"""
		if not output_file.endswith(".gfa"):
			output_file += ".gfa"

		write_gfa(self, set_of_nodes=set_of_nodes, output_file=output_file,
				  append=append, optional_info=optional_info)


	def bfs(self, start, size):
		"""
		Returns a neighborhood of size given around start node
		:param start: starting node for the BFS search
		:param size: size of the neighborhood to return
		"""
		if start not in self.nodes:
			with shelve.open(self.node_chunks) as node_chunk:
				chunk_id = node_chunk[start]
				logger.warning(f"The start node given to bfs {start} not in the graph, loading its chunk")
				self.load_chunk(chunk_id)
				# self.loaded_c.append(chunk_id)
		return bfs(self, start, size)
		# neighborhood = bfs(self, start, size)
		# return neighborhood

	# def output_chunk(self, chunk_id):
	# 	"""
	# 	This function outputs a pickled dict with the chunk's information
	# 	the chunk location should be saved with the graph location
	# 	:param chunk_id: int for the chunk id
	# 	"""
	# 	chunk = dict()
	# 	for n in self.nodes.values():
	# 		if n.chunk_id == chunk_id:
	# 			chunk[n.id] = {"seq":n.seq, "start":n.start, "end":n.end, "chunk":n.chunk, "optional_info":n.optional_info}
	# 	with open(self.graph_name + "chunk" + str(chunk_id), "wb") as outfile:
	# 		pickle.dump(chunk, outfile)
		
	def unload_chunk(self, chunk_id):
		"""
		Unloades a loaded chunk and remove those nodes from the graph
		"""
		# in unload, I need to output the chunk again
		# in case some updates been added to the chunk
		# self.output_chunk(chunk_id)
		to_remove = []
		for n in self.nodes.values():
			if n.chunk_id == chunk_id:
				to_remove.append(n.id)
		# here I am removing the nodes but not the edges associated with it
		# so in case I need to load this again in another traversal for example
		for n in to_remove: 
			del self.nodes[n]
		if chunk_id in self.loaded_c:
			self.loaded_c.remove(chunk_id)

	def load_chunk(self, chunk_id):
		"""
		this function will read a chunk and update the nodes in the graph
		"""
		# print(f"loading chunk {chunk_id}")
		# with open(self.graph_name + "chunk" + str(chunk_id), "rb") as infile:
		# 	chunk = pickle.load(infile)
		if len(self.loaded_c) >= self.loaded_c_limit:
			logger.info(f"There has been 10 chunks loaded, will be unloading old chunks!")
			while len(self.loaded_c) >= self.loaded_c_limit:
				c_id = self.loaded_c.popleft()
				logger.info(f"Unloading chunk {c_id} and current loaded c are {self.loaded_c}")
				self.unload_chunk(c_id)
		logger.info(f"Loading chunk {chunk_id}")
		offset, n_lines = self.offsets[chunk_id]
		self.read_gfa(self.graph_name, offset, n_lines)
		if chunk_id not in self.loaded_c:
			self.loaded_c.append(chunk_id)
		logger.info(f"Loaded chunks so far {self.loaded_c}")

		# for n_id, n in chunk.items():
		# 	# to remove
		# 	if n_id not in self.nodes:
		# 		new_node = Node(n_id)
		# 		new_node.seq = n["seq"]
		# 		new_node.start = n["start"]
		# 		new_node.end = n["end"]
		# 		new_node.chunk_id = n["chunk"]
		# 		new_node.optional_info = ['optional_info']
		# 		self.nodes[n_id] = new_node
			# else:
			# 	print(f"node {n_id} already in graph, skipping...")

	def read_gfa(self, gfa_file_path, offset, n_lines):
		"""
        Read a gfa file
        :param gfa_file_path: gfa graph file.
        :param low_memory: don't read the sequences to save memory
        :return: Dictionary of node ids and Node objects.
        """

		# todo I need to edit this to also take into accounts the tags at the L lines (Maybe)
		gfa_file = open(gfa_file_path, "r")
		gfa_file.seek(offset)
		edges = []
		# min_node_length = k
		for _ in range(n_lines):
			line = gfa_file.readline()
			if line.startswith("S"):
				line = line.strip().split("\t")
				n_id = str(line[1])
				n_len = len(line[2])
				self.nodes[n_id] = Node(n_id)
				self.nodes[n_id].seq = line[2]
				self.nodes[n_id].seq_len = n_len

				tags = line[3:]
				# adding the extra tags if any to the node object
				if tags:
					for tag in tags:
						tag = tag.split(":")
						# I am adding the tags as key:value, key is tag_name:type and value is the value at the end
						# e.g. SN:i:10 will be {"SN": ('i', '10')}
						self.nodes[n_id].tags[tag[0]] = (tag[1], tag[2])  # (type, value)
					self.nodes[n_id].chunk_id = int(self.nodes[n_id].tags['cid'][1])

			elif line.startswith("L"):
				edges.append(line)

		for e in edges:
			line = e.split()

			first_node = str(line[1])
			second_node = str(line[3])
			# todo need to deal with edges that are part of another chunk
			# if first_node not in self.nodes:
			# 	logging.warning(f"an edge between {first_node} and {second_node} exists but a "
			# 					f"node record for {first_node} does not exist in the file. Skipping")
			# 	continue
			# if second_node not in self.nodes:
			# 	logging.warning(f"an edge between {first_node} and {second_node} exists but a "
			# 					f"node record for {second_node} does not exist in the file. Skipping")
			# 	continue

			overlap = int(line[5][:-1])

			if line[2] == "-":
				from_start = True
			else:
				from_start = False

			if line[4] == "-":
				to_end = True
			else:
				to_end = False

			if from_start and to_end:
				if first_node in self.nodes:
					self.nodes[first_node].start.add((second_node, 1, overlap))
				if second_node in self.nodes:
					self.nodes[second_node].end.add((first_node, 0, overlap))
			elif from_start and not to_end:
				if first_node in self.nodes:
					self.nodes[first_node].start.add((second_node, 0, overlap))
				if second_node in self.nodes:
					self.nodes[second_node].start.add((first_node, 0, overlap))
			elif not from_start and not to_end:
				if first_node in self.nodes:
					self.nodes[first_node].end.add((second_node, 0, overlap))
				if second_node in self.nodes:
					self.nodes[second_node].start.add((first_node, 1, overlap))
			elif not from_start and to_end:
				if first_node in self.nodes:
					self.nodes[first_node].end.add((second_node, 1, overlap))
				if second_node in self.nodes:
					self.nodes[second_node].end.add((first_node, 1, overlap))

		gfa_file.close()

	def write_gfa(self, set_of_nodes=None,
				  output_file="output_file.gfa", append=True):
		"""
        Write a gfa out
        :param self: the graph object
        :param set_of_nodes: A list of node ids of the path or nodes we want to generate a GFA file for.
        :param output_file: path to output file
        :param append: if I want to append to a file instead of rewriting it
        :return: writes a gfa file
        """

		if set_of_nodes is None:
			set_of_nodes = self.nodes.keys()

		if append is False:
			f = open(output_file, "w+")
		else:
			if os.path.exists(output_file):
				f = open(output_file, "a")
			else:
				logging.warning("Trying to append to a non-existent file\n"
								"creating an output file")
				f = open(output_file, "w+")

		for n1 in set_of_nodes:
			if n1 not in self.nodes:
				logging.warning("Node {} does not exist in the graph, skipped in output".format(n1))
				continue

			line = self.nodes[n1].to_gfa_line()
			# line = str("\t".join(("S", str(n1), nodes[n1].seq, "LN:i:" + str(len(nodes[n1].seq)))))
			# if optional_info:
			# 	line += "\t" + nodes[n1].optional_info

			f.write(line + "\n")

			# writing edges
			# edges = []
			# overlap = str(graph.k - 1) + "M\n"

			for n in self.nodes[n1].start:
				overlap = str(n[2]) + "M\n"
				# I am checking if there are nodes I want to write
				# I think I can remove this later as I implemented the .remove_node
				# to the Graph class that safely removes a node and all its edges
				# So there shouldn't be any edges to removed
				if n[0] in set_of_nodes:
					if n[1] == 0:
						edge = str("\t".join(("L", str(n1), "-", str(n[0]), "+", overlap)))
						edge += "\n"
						# edges.append(edge)
					else:
						edge = str("\t".join(("L", str(n1), "-", str(n[0]), "-", overlap)))
						edge += "\n"
						# edges.append(edge)
					f.write(edge)

			for n in self.nodes[n1].end:
				overlap = str(n[2]) + "M\n"

				if n[0] in set_of_nodes:
					if n[1] == 0:
						edge = str("\t".join(("L", str(n1), "+", str(n[0]), "+", overlap)))
						edge += "\n"
						# edges.append(edge)
					else:
						edge = str("\t".join(("L", str(n1), "+", str(n[0]), "-", overlap)))
						edge += "\n"
						# edges.append(edge)
					f.write(edge)
			#
			# for e in edges:
			# 	f.write(e)

		f.close()
