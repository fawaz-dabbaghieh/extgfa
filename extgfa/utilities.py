import sys
import pickle
import logging
import shelve
from extgfa.Graph import Graph
import networkx as nx
from collections import defaultdict


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
complement = str.maketrans("ACGTN", "TGCAN")


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


def check_consist(chunk_sizes, graph):
    not_consist = dict()
    for nid, n in graph.nodes.items():
        if n['chunk'] != 0 and n['chunk'] not in chunk_sizes:
            not_consist[nid] = n['chunk']
    return not_consist


def output_csv_colors(graph, chunks, outputfile):
    """
    Outputs colors of original graph based on the subgraphs as a csv file.
    graph: list of nx subgraphs
    outputfile: output file name
    """
    outputfile = outputfile.replace(".gfa", ".csv")
    colors = ["black", "blue", "green", "red", "yellow", "cyan", "magenta", "purple", "brown"]
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
    # todo I need to add a rule to stop merging with chunks that are too big
    to_merge = set()
    for cid, size in chunk_sizes.items():
        if size < threshold:
            to_merge.add(cid)
            # to_merge[cid] = [x for x in graph if graph.nodes[x]['chunk'] == cid]
    logger.info(f"There are {len(to_merge)} chunks to be merged")
    # logger.info(f"There are {len([x for x in chunk_sizes.values() if x < threshold])} chunks to be merged")
    # while min(chunk_sizes.values()) < threshold:
    for chunk_id in to_merge:
        # pdb.set_trace()
        chunk = [x for x in graph if graph.nodes[x]['chunk'] == chunk_id]
        if len(chunk) > threshold:
            continue

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
            new_chunk_id = int(max(neighbor_chunk, key=neighbor_chunk.get))  # merge with most connected neighbor
            logger.info(f"Merging chunk {chunk_id} that contains {chunk_sizes[chunk_id]} nodes with chunk {new_chunk_id}")

            # logger.info(f"Merging chunk {chunk_id} with {chunk_sizes[new_chunk_id]} nodes")
            for n in chunk:
                graph.nodes[n]['chunk'] = new_chunk_id
            chunk_sizes[new_chunk_id] += len(chunk)

            del chunk_sizes[chunk_id]  # removing the old chunk id entry
            # pdb.set_trace()
        # no neighbors to merge with
        else:
            pass
    logger.info(f"There are {len([x for x in chunk_sizes.values() if x < threshold])} chunks to be merged now")


def split_chunk(graph, chunk_sizes, top_threshold, CHUNK_COUNTER, algo):
    """
    When a chunk is too big, gets split again using lv algorithm
    original_graph: the nx graph object
    chunk_sizes: a dictionary of chunk_id:chunk_size
    threshold: threshold for biggest components
    """
    # I think to do it faster, I can take the components that come out of kl algorithm
    # and merge those together, but for now, I'll just collect them all and do the merging later
    if algo == "lv":
        algorithm = nx.community.louvain_communities
    elif algo == "gm":
        algorithm = nx.community.greedy_modularity_communities
    else:
        print("You need to give either lv or gm to split_chunk function")
        sys.exit()

    # global CHUNK_COUNTER
    to_split = dict()
    for cid, size in chunk_sizes.items():
        if size > top_threshold:
            to_split[cid] = [x for x in graph if graph.nodes[x]['chunk'] == cid]

    logger.info(f"There are {len(to_split)} chunks to be split")

    for chunk_id, chunk in to_split.items():

        new_graph = graph.subgraph(chunk)
        logger.info(f"Running Louvian communities algorithm on biggest chunk of length {len(new_graph)}")
        partitions = algorithm(new_graph)

        # for idx, comp in enumerate(partitions):
        for comp in partitions:
            for n in comp:
                # new_graph.nodes[n]['chunk'] = idx + 1 + max_chunk_id
                new_graph.nodes[n]['chunk'] = CHUNK_COUNTER
            chunk_sizes[CHUNK_COUNTER] = len(comp)

            CHUNK_COUNTER += 1
        del chunk_sizes[chunk_id]
    return CHUNK_COUNTER


def final_output(chunk_index, input_gfa, output_gfa):
    # now I have the chunk index, I reload the graph with my class, assign the chunk ids and then output a new
    # graph and the offset index
    logger.info(f"Reloading the GFA with all the information now and assigning the node chunks")
    graph = Graph(input_gfa)
    for idx, chunk in enumerate(chunk_index):
        for n in chunk:
            graph.nodes[n].chunk_id = idx + 1
    n_chunks = len(chunk_index)
    logger.info(f"There are {n_chunks} chunks")
    # del chunk_index

    logger.info(f"Creating the node_id:chunk_id DB")
    outshelve = shelve.open(output_gfa + ".db")
    for n in graph.nodes.keys():
        outshelve[n] = graph[n].chunk_id
    logger.info(f"Shelving the db to {output_gfa}.db")
    outshelve.close()

    logger.info(f"outputting the chunked GFA into {output_gfa}")
    graph.write_chunked_gfa(chunk_index, output_gfa + ".gfa")

    logger.info(f"outputting the chunked GFA offsets into {output_gfa}.index")
    outindex = open(output_gfa + ".index", "wb")
    pickle.dump(graph.chunk_offsets, outindex)

def rev_comp(seq):
    return seq[::-1].translate(complement)