
import sys
import os
import pdb
import time
import gc
import pickle
import logging
import shelve
from extgfa.utilities import gfa_to_nx, output_csv_colors, merge_chunk
from extgfa.Graph import Graph
import networkx as nx
from collections import deque, defaultdict


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

CHUNK_COUNTER = 1


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
    # pdb.set_trace()
    while max(chunk_sizes.values()) > top_threshold:
        chunk_id = int(max(chunk_sizes, key=chunk_sizes.get))
        chunk = [x for x in original_graph if original_graph.nodes[x]['chunk'] == chunk_id]
        del chunk_sizes[chunk_id]

        new_graph = original_graph.subgraph(chunk)
        logger.info(f"Running GM algorithm on biggest chunk of length {len(chunk)}")
        partitions = nx.community.greedy_modularity_communities(new_graph)

        for idx, comp in enumerate(partitions):
            for n in comp:
                # new_graph.nodes[n]['chunk'] = idx + 1 + max_chunk_id
                new_graph.nodes[n]['chunk'] = CHUNK_COUNTER
                # local_chunk_ids.add(idx + 1 + max_chunk_id)
            CHUNK_COUNTER += 1
        # local_chunk_sizes = defaultdict(int)
        for n in new_graph:
            chunk_sizes[new_graph.nodes[n]['chunk']] += 1
            # local_chunk_sizes[new_graph.nodes[n]['chunk']] += 1


def run_gmc(graph, chunk_sizes):
    global CHUNK_COUNTER
    start = time.perf_counter()
    logger.info("running Greedy Modular Communities algorithm first on graph")
    partitions = nx.community.greedy_modularity_communities(graph)
    logger.info(f"It took {time.perf_counter() - start:.2f} seconds to run Greedy Modular Communities")
    logger.info(f"It produced {len(partitions)} communities")
    for idx, comp in enumerate(partitions):
        for n in comp:
            graph.nodes[n]['chunk'] = CHUNK_COUNTER
            chunk_sizes[CHUNK_COUNTER] += 1
        CHUNK_COUNTER += 1
    # pdb.set_trace()
    # chunk_sizes = defaultdict(int)
    # for n in graph:
    #     chunk_sizes[graph.nodes[n]['chunk']] += 1


def gm_main(input_gfa, output_gfa, upper, lower):
    global CHUNK_COUNTER
    # chunk_counter = 1
    chunk_sizes = defaultdict(int)
    to_skip = dict()
    graph = gfa_to_nx(input_gfa)
    logger.info(f"Created the graph from {input_gfa} which has {len(graph.nodes)} nodes")
    # todo need to make the upper and lower threshold user changeable

    top_threshold = len(graph) / upper
    btm_threshold = len(graph) / lower

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

            logger.info("Running Greedy Modularity Communities algorithm on component")
            run_gmc(new_graph, chunk_sizes)
            logger.info(f"We have {len(chunk_sizes)} chunks")
            logger.info("Now further splitting chunks that are bigger than the threshold")
            split_chunk(new_graph, chunk_sizes, top_threshold)
            # todo solve the bug when merging, sometimes it throws an error in chunk_index[sorted_chunks[cid]].append(n)
            logger.info("Now merging smaller chunks")
            merge_chunk(graph, chunk_sizes, btm_threshold)
            logger.info(f"Now we have {len(chunk_sizes)} chunks after merging")

    # assert len(set(chunk_sizes.keys()).intersection(to_skip.keys())) == 0
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
    # for c in final_chunks.keys():
    #     chunk_index.append([x for x in graph if graph.nodes[x]['chunk'] == c])
    #     assert len(chunk_index[-1]) == final_chunks[c]

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
    print(f"There are {n_chunks} chunks")
    # del chunk_index

    logger.info(f"Creating the node_id:chunk_id DB")
    outshelve = shelve.open(output_gfa + ".db")
    for n in graph.nodes.keys():
        outshelve[n] = graph[n].chunk_id
    logger.info(f"Shelving the db to {output_gfa}.db")
    outshelve.close()

    logger.info(f"outputting the chunked GFA into {output_gfa}")
    graph.write_chunked_gfa(chunk_index, output_gfa)

    logger.info(f"outputting the chunked GFA offsets into {output_gfa}.index")
    outindex = open(output_gfa + ".index", "wb")
    pickle.dump(graph.chunk_offsets, outindex)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("You need to give the input GFA file and output GFA file")
        sys.exit()
    gm_main(sys.argv[1], sys.argv[2])
