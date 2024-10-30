import pdb
import time
import gc
import logging
from extgfa.utilities import gfa_to_nx, output_csv_colors, merge_chunk, split_chunk, final_output
import networkx as nx


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

CHUNK_COUNTER = 1


def run_gmc(graph, chunk_sizes):
    global CHUNK_COUNTER
    start = time.perf_counter()
    logger.info("running Greedy Modular Communities algorithm first on graph")
    partitions = nx.community.greedy_modularity_communities(graph)
    logger.info(f"It took {time.perf_counter() - start:.2f} seconds to run Greedy Modular Communities")
    logger.info(f"It produced {len(partitions)} communities")
    # for idx, comp in enumerate(partitions):
    for comp in partitions:
        for n in comp:
            graph.nodes[n]['chunk'] = CHUNK_COUNTER

        chunk_sizes[CHUNK_COUNTER] = len(comp)
        CHUNK_COUNTER += 1


def gm_main(input_gfa, output_gfa, upper, lower):
    global CHUNK_COUNTER
    # chunk_counter = 1
    chunk_sizes = dict()
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
            counter = CHUNK_COUNTER
            CHUNK_COUNTER = split_chunk(new_graph, chunk_sizes, top_threshold, counter, algo = 'gm')

            logger.info("Now merging smaller chunks")
            merge_chunk(graph, chunk_sizes, btm_threshold)
            logger.info(f"Now we have {len(chunk_sizes)} chunks after merging")

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
    output_csv_colors(graph, chunk_sizes, output_gfa)

    del graph
    del new_graph
    gc.collect()

    final_output(chunk_index, input_gfa, output_gfa)
