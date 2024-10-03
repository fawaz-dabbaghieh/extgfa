import os
import sys
import pdb
import logging
from extgfa.bfs import bfs

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')


class Node:
    __slots__ = ("id", "seq", "seq_len", "start", "end", "visited", "tags", "chunk_id")

    def __init__(self, identifier):
        self.id = identifier
        self.seq = ""
        self.seq_len = 0
        self.start = set()
        self.end = set()
        self.visited = False
        self.tags = dict()
        self.chunk_id = 0

    def __len__(self):
        return self.seq_len

    def neighbors(self):
        """
        Returns all adjacent nodes' ids to self
        """
        neighbors = [x[0] for x in self.start] + [x[0] for x in self.end]
        return sorted(neighbors)

    def in_direction(self, other, direction):
        """
        returns true if other is a neighbor in that direction, false otherwise
        """
        if direction == 0:
            if other in [x[0] for x in self.start]:
                return True
            return False
        elif direction == 1:
            if other in [x[0] for x in self.end]:
                return True
            return False
        else:
            raise ValueError(
                f"Trying to access a wrong direction in node {self.id}, give 0 for start or 1 for end"
            )

    def children(self, direction):
        """
        returns the children of a node in given direction
        """
        if direction == 0:
            return [x[0] for x in self.start]
        elif direction == 1:
            return [x[0] for x in self.end]
        else:
            raise ValueError(
                f"Trying to access a wrong direction in node {self.id}, give 0 for start or 1 for end"
            )

    def remove_from_start(self, neighbor, side, overlap):
        """
        remove the neighbor edge from the start going to side in neighbor
        """
        assert side in {1, 0}
        try:
            self.start.remove((neighbor, side, overlap))
        except KeyError:
            logging.warning(
                f"Could not remove edge {(neighbor, side, overlap)} from {self.id}'s start as it does not exist"
            )

    def remove_from_end(self, neighbor, side, overlap):
        """
        remove the neighbor edge from the end going to side in neighbor
        """
        assert side in {1, 0}
        try:
            self.end.remove((neighbor, side, overlap))
        except KeyError:
            logging.warning(
                f"Could not remove edge {(neighbor, side, overlap)} from {self.id}'s end as it does not exist"
            )

    def add_from_start(self, neighbor, side, overlap):
        """
        add edge between self.start and neighbor
        """
        assert side in {1, 0}
        self.start.add((neighbor, side, overlap))

    def add_from_end(self, neighbor, side, overlap):
        """
        add edge between self.end and neighbor
        """
        assert side in {1, 0}
        self.end.add((neighbor, side, overlap))

    def to_gfa_line(self, with_seq=True):
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


class Graph:
    """
    Graph object containing the important information about the graph
    """

    __slots__ = ['nodes', 'chunk_offsets']

    def __init__(self, graph_file=None):
        self.nodes = dict()
        self.chunk_offsets = dict()
        if graph_file is not None:
            if not os.path.exists(graph_file):
                print("Error! Check log file.")
                logger.error("graph file {} does not exist".format(graph_file))
                sys.exit()
            # loading nodes from file
            self.read_gfa(gfa_file_path=graph_file)

    def __len__(self):
        """
        overloading the length function
        """
        return len(self.nodes)

    def __str__(self):
        """
        overloading the string function for printing
        """
        return "The graph has {} Nodes".format(len(self.nodes))

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
            return None

    def __setitem__(self, key, value):
        """
        overloading setting an item in nodes
        """
        if isinstance(value, Node):
            self.nodes[key] = value
        else:
            raise ValueError("the object given to set should be a Node object")

    def __delitem__(self, key):
        """
        overloading deleting item
        """
        del self.nodes[key]

    def reset_visited(self):
        """
        resets all nodes.visited to false
        """
        for n in self.nodes.values():
            n.visited = False

    def neighbors(self, node_id):
        """
        Returns all adjacent nodes' ids to self
        """
        neighbors = [x[0] for x in self.nodes[node_id].start] + [x[0] for x in self.nodes[node_id].end]
        return neighbors

    def children(self, node, direction):
        """
        returns the children of a node in given direction
        """
        if node in self.nodes:
            if direction == 0:
                return [(x[0], x[1]) for x in self.nodes[node].start]
            elif direction == 1:
                return [(x[0], x[1]) for x in self.nodes[node].end]
            else:
                raise ValueError(
                    f"Trying to access a wrong direction in node {self.id}, give 0 for start or 1 for end"
                )
        else:
            pdb.set_trace()
            raise KeyError(f"Node {node} is not in the graph")

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

    def remove_lonely_nodes(self):
        """
        remove singular nodes with no neighbors
        """
        nodes_to_remove = [n.id for n in self.nodes.values() if len(n.neighbors()) == 0]
        for i in nodes_to_remove:
            self.remove_node(i)

    def bfs(self, start_node, size):
        return bfs(self, start_node, size)

    def write_chunked_gfa(self, chunks, output_file="output_file.gfa"):
        """
        Write a gfa out
        n_chunks: the number of chunks that are now ordered from 1 to n_chunks + 1
        output_file: path to output file
        """

        # if os.path.exists(output_file):
        #     logger.error(f"File {output_file} already exists")
        #     sys.exit()
        # else:
        #     f = open(output_file, "w")

        f = open(output_file, "w")
        chunk_pos_counter = 0
        for idx, chunk in enumerate(chunks):
        # for cid in range(1, n_chunks + 1):
        #     if cid == 1:  # first chunk has offset 0
        #         self.chunk_offsets[cid] = [0, 0]
        #     else:
        #         self.chunk_offsets[cid] = [chunk_pos_counter, 0]
        #     set_of_nodes = [n for n in self.nodes.keys() if self.nodes[n].chunk_id == cid]
            if idx == 0:
                self.chunk_offsets[1] = [0, 0]
            else:
                self.chunk_offsets[idx + 1] = [chunk_pos_counter, 0]
            set_of_nodes = chunk
            idx += 1
            for n1 in set_of_nodes:
                if n1 not in self:
                    logging.warning("Node {} does not exist in the graph, skipped in output".format(n1))
                    continue

                line = self.nodes[n1].to_gfa_line()
                line += "\n"

                f.write(line)
                chunk_pos_counter += len(line)
                self.chunk_offsets[idx][1] += 1

                for n in self.nodes[n1].start:
                    overlap = str(n[2]) + "M"
                    if n[1] == 0:
                        edge = str("\t".join(("L", str(n1), "-", str(n[0]), "+", overlap)))
                        edge += "\n"

                    else:
                        edge = str("\t".join(("L", str(n1), "-", str(n[0]), "-", overlap)))
                        edge += "\n"

                    f.write(edge)
                    chunk_pos_counter += len(edge)
                    self.chunk_offsets[idx][1] += 1

                for n in self.nodes[n1].end:
                    overlap = str(n[2]) + "M"

                    if n[1] == 0:
                        edge = str("\t".join(("L", str(n1), "+", str(n[0]), "+", overlap)))
                        edge += "\n"

                    else:
                        edge = str("\t".join(("L", str(n1), "+", str(n[0]), "-", overlap)))
                        edge += "\n"

                    f.write(edge)
                    chunk_pos_counter += len(edge)
                    self.chunk_offsets[idx][1] += 1

            # self.chunk_offsets[cid][1] -= 1  # not sure why, but I need an offset by 1 at the end
        f.close()

    def read_gfa(self, gfa_file_path):
        """
        Read a gfa file
        :param gfa_file_path: gfa graph file.
        :param low_memory: don't read the sequences to save memory
        :return: Dictionary of node ids and Node objects.
        """
        if not os.path.exists(gfa_file_path):
            logging.error("the gfa file path you gave does not exists, please try again!")
            sys.exit()

        edges = []
        # min_node_length = k
        with open(gfa_file_path, "r") as lines:
            for line in lines:
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

                elif line.startswith("L"):
                    edges.append(line)

        for e in edges:
            line = e.split()

            first_node = str(line[1])
            second_node = str(line[3])
            if first_node not in self:
                logging.warning(f"an edge between {first_node} and {second_node} exists but a "
                                f"node record for {first_node} does not exist in the file. Skipping")
                continue
            if second_node not in self:
                logging.warning(f"an edge between {first_node} and {second_node} exists but a "
                                f"node record for {second_node} does not exist in the file. Skipping")
                continue

            overlap = int(line[5][:-1])

            if line[2] == "-":
                from_start = True
            else:
                from_start = False

            if line[4] == "-":
                to_end = True
            else:
                to_end = False

            if from_start and to_end:  # from start to end L x - y -
                if (second_node, 1, overlap) not in self.nodes[first_node].start:
                    self.nodes[first_node].start.add((second_node, 1, overlap))
                if (first_node, 0, overlap) not in self.nodes[second_node].end:
                    self.nodes[second_node].end.add((first_node, 0, overlap))

            elif from_start and not to_end:  # from start to start L x - y +

                if (second_node, 0, overlap) not in self.nodes[first_node].start:
                    self.nodes[first_node].start.add((second_node, 0, overlap))

                if (first_node, 0, overlap) not in self.nodes[second_node].start:
                    self.nodes[second_node].start.add((first_node, 0, overlap))

            elif not from_start and not to_end:  # from end to start L x + y +
                if (second_node, 0, overlap) not in self.nodes[first_node].end:
                    self.nodes[first_node].end.add((second_node, 0, overlap))

                if (first_node, 1, overlap) not in self.nodes[second_node].start:
                    self.nodes[second_node].start.add((first_node, 1, overlap))

            elif not from_start and to_end:  # from end to end L x + y -
                if (second_node, 1, overlap) not in self.nodes[first_node].end:
                    self.nodes[first_node].end.add((second_node, 1, overlap))

                if (first_node, 1, overlap) not in self.nodes[second_node].end:
                    self.nodes[second_node].end.add((first_node, 1, overlap))
