import sys
import pdb
from collections import defaultdict
import networkit as nk
from extgfa.Graph import Graph


def node_map(node_order_file):
    node_map = {}
    counter = 0
    with open(node_order_file, "r") as f:
        for line in f:
            node_map[counter] = line.strip()
            # node_map[line.strip()] = counter
            counter += 1
    return node_map


def run_community_detection(metis_file):
    # Load the METIS graph
    com_count = defaultdict(list)

    graph = nk.readGraph(metis_file, nk.Format.METIS)

    # Run community detection using PLM (Parasitic Label Propagation)
    plm = nk.community.PLM(graph)
    plm.run()

    # Get the communities as a Partition object
    communities = plm.getPartition()
    # pdb.set_trace()
    for i in range(graph.numberOfNodes()):
        com_count[communities.subsetOf(i)].append(i)
    # Get the number of communities and the average number of nodes per community

    avg_nodes_per_community = sum([len(x) for x in com_count.values()]) / len(com_count)
    # Print the results
    print(f"Number of communities: {len(com_count)}")
    print(f"Average number of nodes per community: {avg_nodes_per_community:.2f}")
    return com_count


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("You need to give the input METIS file, the input GFA and the nodes order")
        sys.exit()
    metis_file = sys.argv[1]
    gfa_file = sys.argv[2]
    node_order_file = sys.argv[3]
    print(f"Running PLM on {metis_file}")
    com_counts = run_community_detection(metis_file)
    node_map = node_map(node_order_file)
    # example community
    ex_com = int(len(com_counts)/2)
    node_set = set(com_counts[ex_com])
    # for i in com_counts[ex_com]:
    #     node_set.add(node_map[i])

    pdb.set_trace()
    # graph = Graph(gfa_file, low_mem=True)
    # for n in graph.nodes.keys():
    #     graph.nodes[n].community = communities.subsetOf(node_map[n])

