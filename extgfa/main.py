import sys
import os
import argparse
import logging
from extgfa.__version__ import version
from extgfa.greedy_modularity_communities_partitioning import gm_main
from extgfa.kl_algorithm_partitioning import kl_main
from extgfa.louvian_partitioning import lv_main

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

# todo add argparse and have two subcommands, one is for partitioning and one for bfs
def main():
    print(f"Running version {version}")
    if len(sys.argv) < 6:
        print("you need to give algorithm type, input GFA, output GFA, upper threshold, lower threshold")
        print("Algorithms type are gm for greedy modularity, kl for kernighan lin algorithm, or lv for louvian")
        sys.exit()

    if sys.argv[1] not in {'gm', 'kl', 'lv'}:
        print(f"input type {sys.argv[1]} not supported")
        print("gm or kl for greedy modularity or kernighan lin algorithms")
        sys.exit()

    if not os.path.exists(sys.argv[2]):
        print(f"input file {sys.argv[2]} does not exist")
        sys.exit()

    if sys.argv[2].endswith(".gz"):
        print("You need to provide an uncompressed GFA file")
        sys.exit()

    if os.path.exists(sys.argv[3]):
        print(f"The file given for output {sys.argv[3]} already exists")
        sys.exit()

    try:
        upper, lower = int(sys.argv[4]), int(sys.argv[5])
        if lower > upper:
            print(f"the lower threshold cannot be bigger than the upper threshold")
            sys.exit()

    except ValueError:
        print("upper and lower threshold must be integers")
        sys.exit()

    output_gfa = sys.argv[3].replace(".gfa", "")
    args = [sys.argv[2], output_gfa, upper, lower]
    if sys.argv[1] == 'gm':
        gm_main(*args)

    if sys.argv[1] == "kl":
        kl_main(*args)

    if sys.argv[1] == "lv":
        print("Running Louvian communities algorithm")
        lv_main(*args)