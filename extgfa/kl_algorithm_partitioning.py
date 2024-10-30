"""
Does KL algorithm guarantees that the partitions are a connected component?
No, the Kernighan-Lin (KL) algorithm does not guarantee that each partition will be a connected component.

The KL algorithm is a heuristic for graph partitioning that aims to minimize the edge cut between two partitions
while keeping the partitions balanced in size. It operates by iteratively swapping pairs of nodes between two partitions
 to reduce the edge cut. However, it does not explicitly enforce or ensure that each partition forms a connected
 component. As a result, after applying the KL algorithm, it's possible that the nodes within a partition are not all
 connected, leading to partitions that may consist of multiple disconnected subgraphs.

If having connected components in each partition is required, additional constraints or post-processing steps would
need to be applied after the KL algorithm is executed.
"""
import sys
import pdb
import gc
import logging
from extgfa.utilities import gfa_to_nx, output_csv_colors, merge_chunk, final_output
import networkx as nx
from collections import defaultdict


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


def kl_main(input_gfa, output_gfa, top_threshold, btm_threshold):
    # chunk_counter = 1
    global CHUNK_COUNTER
    chunk_sizes = defaultdict(int)
    to_skip = dict()
    graph = gfa_to_nx(input_gfa)
    if top_threshold > len(graph):
        logger.error(f"The upper threshold given {top_threshold} is bigger than the graph given {input_gfa}")
        sys.exit(1)
    logger.info(f"Created the graph from {input_gfa} which has {len(graph.nodes)} nodes")
    # top_threshold = len(graph) / upper
    # btm_threshold = len(graph) / lower
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

    # assert len(set(chunk_sizes.keys()).intersection(to_skip.keys())) == 0
    chunk_index = []
    sorted_chunks = dict()
    counter = 0
    for cid, size in chunk_sizes.items():
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
    output_csv_colors(graph, chunk_sizes, output_gfa + ".csv")

    del graph
    del new_graph
    gc.collect()

    final_output(chunk_index, input_gfa, output_gfa)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("You need to give the input GFA file and output GFA file")
        sys.exit()
    kl_main(sys.argv[1], sys.argv[2])