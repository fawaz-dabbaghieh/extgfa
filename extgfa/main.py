import sys
import os
import argparse
import logging
from extgfa.greedy_modularity_communities_partitioning import gm_main
from extgfa.kl_algorithm_partitioning import kl_main
from extgfa.louvian_partitioning import lv_main


# todo add argparse and have two subcommands, one is for partitioning and one for bfs
def main():
    if len(sys.argv) < 6:
        print("you need to give algorithm type, input GFA, output GFA, upper threshold, lower threshold")
        print("Algorithms type are gm for greedy modularity, kl for kernighan lin algorithm, or lv for louvian")
        sys.exit()

    if not os.path.exists(sys.argv[2]):
        print(f"input file {sys.argv[2]} does not exist")
        sys.exit()

    if sys.argv[1] not in {'gm', 'kl', 'lv'}:
        print(f"input type {sys.argv[1]} not supported")
        print("gm or kl for greedy modularity or kernighan lin algorithms")
        sys.exit()
    try:
        upper, lower = int(sys.argv[4]), int(sys.argv[5])
        if upper > lower:
            print(f"The upper threshold has to be smaller than lower (n_nodes/threshold)")
            sys.exit()

    except ValueError:
        print("upper and lower threshold must be integers")
        sys.exit()

    if sys.argv[1] == 'gm':
        gm_main(sys.argv[2], sys.argv[3], upper, lower)

    if sys.argv[1] == "kl":
        kl_main(sys.argv[2], sys.argv[3], upper, lower)

    if sys.argv[1] == "lv":
        lv_main(sys.argv[2], sys.argv[3], upper, lower)