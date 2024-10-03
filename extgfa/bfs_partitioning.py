import sys
import os
import pdb
import time
import gc
import pickle
import logging
import shelve
from extgfa.Graph import Graph
import networkx as nx
from collections import deque, defaultdict


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

CHUNK_COUNTER = 1

def main_while_loop(graph, start_node, queue, visited, size):
    neighborhood = {start_node}
    if len(queue) == 0:
        queue.append(start_node)

    while len(neighborhood) <= size and len(queue) > 0:
        start = queue.popleft()
        if start not in neighborhood:
            neighborhood.add(start)
        visited.add(start)
        neighbors = list(graph[start].keys())

        for n in neighbors:
            if graph.nodes[n]['chunk'] != 0:  # means n is already assigned to some chunk, skip
                continue
            if n not in visited and n not in queue:
                queue.append(n)

    return neighborhood


def bfs(graph, start_node, size):
    """
    Runs bfs and returns the neighborhood smaller than size
    Using only bfs was resulting in a one-sided neighborhood.
    So the neighborhood I was getting was mainly going from the start node
    into one direction because we have FIFO and it basically keeps going
    in that direction. So I decided to split check if have two possible directions
    From start, too look in both directions separately and add that to the whole neighborhood
    :param graph: A graph object from class Graph
    :param start_node: starting node for the BFS search
    :param size: size of the neighborhood to return
    """
    global CHUNK_COUNTER
    queue = deque()
    visited = set()
    if size > len(graph):
        size = len(graph) - 1

    queue.append(start_node)
    visited.add(start_node)
    neighbors = graph[start_node].neighbors()

    if len(neighbors) == 0:  # no neighbors
        return {start_node}

    neighborhood = main_while_loop(graph, start_node, queue, visited, size)
    for n in neighborhood:
        graph.nodes[n]['chunk'] = CHUNK_COUNTER
    CHUNK_COUNTER += 1
    return neighborhood


def gfa_to_nx(gfa_file):
    """
    Converts GFA file to NetworkX graph
    :param gfa_file: GFA file
    """
    graph = nx.Graph()
    with open(gfa_file) as f:
        for line in f:
            if line.startswith('S'):
                line = line.strip().split()
                graph.add_node(line[1], chunk=0)
    # reading twice because if I use only add_edge, nodes without edges won't be added to the graph
    # and I don't want to keep all the L lines in a list, this might take too much memory if the graph is big
    with open(gfa_file) as f:
        for line in f:
            if line.startswith('L'):
                line = line.strip().split()
                graph.add_edge(line[1], line[3])
                if "chunk" not in graph.nodes[line[1]]:
                    graph.nodes[line[1]]['chunk'] = 0
                if "chunk" not in graph.nodes[line[3]]:
                    graph.nodes[line[3]]['chunk'] = 0
    return graph


def output_csv_colors(graph, chunks, outputfile):
    """
    Outputs colors of original graph based on the subgraphs as a csv file.
    graph: list of nx subgraphs
    outputfile: output file name
    """
    outputfile = outputfile.replace(".gfa", ".csv")
    colors = ["black", "blue", "green", "red", "yellow", "cyan", "magenta", "purple"]
    chunk_colors = {x:colors[idx % len(colors)] for idx, x in enumerate(list(chunks.keys()))}
    with open(outputfile, 'w') as f:
        f.write("Name,Colour\n")
        for n in graph:
            f.write(f"{n},{chunk_colors[graph.nodes[n]['chunk']]}\n")


def merge_chunk(graph, chunk_sizes, threshold):
    """
    takes a chunk and tries to merge it with the most common neighboring chunk
    chunk_sizes: a dictionary with chunk id and size of chunk
    graph: the nx graph object
    """
    logger.info(f"There are {len([x for x in chunk_sizes.values() if x < threshold])} chunks to be merged")
    while min(chunk_sizes.values()) < threshold:
        chunk_id = int(min(chunk_sizes, key=chunk_sizes.get))
        chunk = [x for x in graph if graph.nodes[x]['chunk'] == chunk_id]
        # if len(chunk) == 1:
        #     pdb.set_trace()
        logger.info(f"Merging chunk {chunk_id} with {chunk_sizes[chunk_id]} nodes")
        # if chunk is small, I can merge it with another chunk
        # I can just look through all the children of the nodes
        # in this chunk and if take a majority vote on which is the most
        # neighboring chunk and I merge the current one with that
        neighbor_chunk = defaultdict(int)
        # neighbor_chunk = [0] * graph.n_chunks
        # print(graph.n_chunks)
        for n in chunk:
            for nn in graph[n].keys():  # nx node neighbors
                # counting neighboring chunks
                if graph.nodes[nn]['chunk'] != chunk_id:
                    neighbor_chunk[graph.nodes[nn]['chunk']] += 1

        # all nodes should have a chunk id
        assert 0 not in neighbor_chunk

        if neighbor_chunk:  # there are neighboring chunks to merge with
            new_chunk_id = int(max(neighbor_chunk, key=neighbor_chunk.get))
            for n in chunk:
                graph.nodes[n]['chunk'] = new_chunk_id
            chunk_sizes[new_chunk_id] += len(chunk)

            del chunk_sizes[chunk_id]  # removing the old chunk id entry
        else:  # if the graph is one big connected component, it should always have neighboring chunks
            pass
    logger.info(f"There are {len([x for x in chunk_sizes.values() if x < threshold])} chunks to be merged now")

def split_chunk(original_graph, chunk_sizes, top_threshold):
    """
    When a chunk is too big, gets split again using KL algorithm
    original_graph: the nx graph object
    chunk_sizes: a dictionary of chunk_id:chunk_size
    threshold: threshold for biggest components
    """
    # I think to do it faster, I can take the components that come out of kl algorithm
    # and merge those together, but for now, I'll just collect them all and do the merging later
    global CHUNK_COUNTER
    while max(chunk_sizes.values()) > top_threshold:
        chunk_id = int(max(chunk_sizes, key=chunk_sizes.get))
        chunk = [x for x in original_graph if original_graph.nodes[x]['chunk'] == chunk_id]
        del chunk_sizes[chunk_id]

        new_graph = original_graph.subgraph(chunk)
        logger.info(f"Running KL algorithm on biggest chunk of length {len(chunk)}")
        bisection = nx.community.kernighan_lin_bisection(new_graph, seed=10)
        logger.info("finding components")
        components = []
        # max_chunk_id = max(chunk_sizes.keys())
        for b in bisection:
            subgraph = new_graph.subgraph(b)
            for c in nx.components.connected_components(subgraph):
                components.append(c)
        del bisection

        # local_chunk_ids = set()
        for idx, comp in enumerate(components):
            for n in comp:
                # new_graph.nodes[n]['chunk'] = idx + 1 + max_chunk_id
                new_graph.nodes[n]['chunk'] = CHUNK_COUNTER
                # local_chunk_ids.add(idx + 1 + max_chunk_id)
            CHUNK_COUNTER += 1
        # local_chunk_sizes = defaultdict(int)
        for n in new_graph:
            chunk_sizes[new_graph.nodes[n]['chunk']] += 1
            # local_chunk_sizes[new_graph.nodes[n]['chunk']] += 1

def run_kl(graph, chunk_sizes):
    """
    Runs KL algorithm on a graph nx object
    """
    global CHUNK_COUNTER
    logger.info("running KL algorithm first time")
    # I keep the seed to always get the same result when running on the same graph
    bisection = nx.community.kernighan_lin_bisection(graph, seed=10)
    logger.info("finding components")
    components = []
    for b in bisection:
        subgraph = graph.subgraph(b)
        for c in nx.components.connected_components(subgraph):
            components.append(c)

    for idx, comp in enumerate(components):
        for n in comp:
            graph.nodes[n]['chunk'] = CHUNK_COUNTER
        CHUNK_COUNTER += 1
    # chunk_sizes = defaultdict(int)
    for n in graph:
        chunk_sizes[graph.nodes[n]['chunk']] += 1
    # emptying some memory
    # del components
    # del bisection
    # gc.collect()
    # return chunk_sizes

def debug(graph, chunk_sizes):
    for cid, size in chunk_sizes.items():
        try:
            assert len([x for x in graph if graph.nodes[x]['chunk'] == cid]) == size
        except AssertionError:
            print(f"chunk id {cid} did not match size {size}")


def kl_main(input_gfa, output_gfa):
    # chunk_counter = 1
    global CHUNK_COUNTER
    chunk_sizes = defaultdict(int)
    to_skip = dict()
    graph = gfa_to_nx(input_gfa)
    logger.info(f"Created the graph from {input_gfa} which has {len(graph.nodes)} nodes")
    top_threshold = len(graph) / 10
    btm_threshold = len(graph) / 50
    for comp in nx.components.connected_components(graph):
        logger.info(f"Got component of length {len(comp)}")
        # component is small enough to be its own chunk without further partitioning
        if len(comp) < top_threshold:
            to_skip[CHUNK_COUNTER] = len(comp)
            for n in comp:
                if graph.nodes[n]['chunk'] != 0:
                    pdb.set_trace()
                graph.nodes[n]['chunk'] = CHUNK_COUNTER
            # to_skip.append(chunk_counter)
            CHUNK_COUNTER += 1
            # chunk_counter = max(chunk_sizes.keys()) + 1
        else:
            new_graph = graph.subgraph(comp)

            logger.info("Running KL algorithm on component")
            run_kl(new_graph, chunk_sizes)
            logger.info(f"We have {len(chunk_sizes)} chunks")
            logger.info("Now splitting bigger chunks")
            split_chunk(new_graph, chunk_sizes, top_threshold)
            logger.info(f"We have {len(chunk_sizes)} chunks after further splitting")
            logger.info("Now merging smaller chunks")
            merge_chunk(new_graph, chunk_sizes, btm_threshold)
            logger.info(f"Now we have {len(chunk_sizes)} chunks after merging")

    final_chunks = chunk_sizes | to_skip
    chunk_index = []
    sorted_chunks = dict()
    counter = 0
    for cid, size in final_chunks.items():
        sorted_chunks[cid] = counter
        chunk_index.append([])
        counter += 1
    for n in graph:
        cid = graph.nodes[n]['chunk']
        chunk_index[sorted_chunks[cid]].append(n)

    logger.info(f"Outputting the CSV file")
    output_csv_colors(graph, final_chunks, output_gfa)

    del graph
    del new_graph
    gc.collect()

    # now I have the chunk index, I reload the graph with my class, assign the chunk ids and then output a new
    # graph and the offset index
    logger.info(f"Reloading the GFA with all the information now and assigning the node chunks")
    graph = Graph(input_gfa)
    for idx, chunk in enumerate(chunk_index):
        for n in chunk:
            graph.nodes[n].chunk_id = idx + 1
    n_chunks = len(chunk_index)
    del chunk_index

    logger.info(f"Creating the node_id:chunk_id DB")
    outshelve = shelve.open(output_gfa + ".db")
    for n in graph.nodes.keys():
        outshelve[n] = graph[n].chunk_id
    logger.info(f"Shelving the db to {output_gfa}.db")
    outshelve.close()

    logger.info(f"outputting the chunked GFA into {output_gfa}")
    graph.write_chunked_gfa(n_chunks, output_gfa)

    logger.info(f"outputting the chunked GFA offsets into {output_gfa}.index")
    outindex = open(output_gfa + ".index", "wb")
    pickle.dump(graph.chunk_offsets, outindex)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("You need to give the input GFA file and output GFA file")
        sys.exit()
    kl_main(sys.argv[1], sys.argv[2])