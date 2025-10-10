from extgfa.Graph import Graph

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
