**extgfa** is a proof-of-concept implementation for an external-memory [GFA](https://gfa-spec.github.io/GFA-spec/GFA1.html)
representation. This implementation provides both
some sort of index, and a graph class that can use that index to only load smaller parts of the graph and not load the complete graph
in memory.
This is especially useful when the user only want to look at or extract a small part of the graph. The user does not
need to care about how internally the class deals with loading and unloading parts of the graph, this is done seemliness behind the scenes.

- [Idea](#idea)
- [Pipeline](#pipeline)
    + [Graph Partitioning](#graph-partitioning)
- [Graph Class](#graph-class)
- [Usage and Examples](#usage-and-examples)
    + [HPRC Minigraph Chr22 Example](#hprc-minigraph-chr22-example)

# Idea
The idea here is inspired by [Minecraft](https://minecraft.fandom.com/wiki/Minecraft_Wiki).
Where in Minecraft, the map is cut into [chunks](https://minecraft.fandom.com/wiki/Chunk)
of 16 by 16 blocks, and chunks are stored
on disk; only chunks that are close to the player are loaded into memory. When the player moves in a certain direction, further
away chunks are unloaded, and closer chunks loaded.

Looking at the figure below, the block or chunk in green is where the chunk and all its institutes are loaded into memory,
the chunks in red that are furthest from the player in the middle are the chunks that are unloaded yet. For Minecraft, they also
have two types of chunk-loading levels, here in yellow and orange, where some aspects of the chunks are loaded and some are not, e.g.
textures are loaded, but animals are not for example.

<p align="center">
    <img src="figures/minecraft_map_chunks.png" alt="drawing" width="300"/>
</p>

In genome graph world, one of the current problems with processing big graphs in the GFA format is that we need to read
the complete file and libraries that use GFAs tend to load the complete graph in memory.
While depending on what the application is, this might not be necessary.
For example, if the user would like to only look at a small part of the graph, or just few nodes, the user still needs to read the complete GFA file
and load the complete graph in memory.

Following this logic, we investigated whether a similar mechanism to Minecraft can be used for genome graphs in GFA format.
In other words, we split the graph into smaller connected neighborhoods (chunks), and store those in a way that we can retrieve
only the chunk when needed and not load the complete graph. In the following section we explain how we achieved that.


# Pipeline
First, we need to partition the graph into smaller neighborhoods or chunks, then store this chunks in a way that we can
easily retrieve them.
In order to do that, we have two steps: cutting the graph into chunks and outputting a reordered GFA with indexes.

## Graph Partitioning
There are many graph algorithms that cut the graph into smaller parts, or find connected neighborhoods. We tested three
algorithms implemented in the `NetworkX` library, the Kernighan-Lin algorithm, edge betweenness partition, Louvian communities,
and Clauset-Newman-Moore greedy modularity maximization algorithm.

At the moment, the user can choose between Kernighan-Lin, Louvian communities, or Clauset-Newman-Moore algorithm for partitioning
the graph into chunks. However, after testing a couple of graphs, we found that Clauset-Newman-Moore algorithm works best,
it's relative fast even for big graphs and produces size-balanced chunk.

The user can also specify a top and bottom thresholds: (1) Top threshold is the limit of a chunk size, i.e. if a chunk
has more than nodes than the top threshold, this chunk will be split further using the chosen algorithm. (2) Bottom threshold
is the lower limit of a chunk size before it gets merged, i.e. if a chunk has less nodes than the bottom threshold, this chunk
will be merged with a neighboring chunk if available.

Once the graph is partitioned into chunk, each chunk is assigned an ID arbitrarily from 0 to _N_ where _N_ is the number of chunks.
We then produce 3 files:

1. Reordered GFA file: **extgfa** produces a new GFA that is similar to the input GFA file.
However, the S and L lines are ordered in such a way, that the nodes and edges that belong to one chunk are written consecutively in the GFA file.
We also keep track of the output file offset where that chunk started in the output GFA file and the number of lines for that chunk.
Therefore, this allows us to retrieve a chunk from the reordered GFA file without having to read the complete file.
2. Chunk offset index: Simply, this is a `pickled` dictionary where the key is the integer chunk ID, and the value is tuple of
two values, the first is the offset number in the reordered GFA output and the second is the number of lines to read starting from that offset.
3. `dbm` file written using `shelve`: A key-value external database where the key is the node ID and the value is the chunk ID.
This database is not loaded into memory and can be used to figure out which chunk ID to load when encountering a node that is not loaded yet.

So, **extgfa** takes a GFA graph as an input and produces three files: reordered GFA, pickled index, `dbm` database.


<p align="center">
    <img src="figures/distgfa_pipeline_v3.png" alt="drawing" width="800"/>
</p>

# Installation
**extgfa** is a simple python package and can be installed with `python3 setup.py install` or from the package directory running
`pip install .`.

Once installed, it can be used a command line tool for creating the chunked graph,
or the user can simply import `from extgfa.Graph import Graph` or `from extgfa.ChGraph import ChGraph`, 
import and use the graph classes implemented.

# Graph Class
Two GFA graph classes are implemented in **extgfa**, both can be imported and used in your own scripts. One is called `extgfa.Graph`,
this class loads the complete GFA graph and can be given any GFA file. The second one is called `extgfa.ChGraph`, and is used for
the chunked graphs, this class requires the reordered GFA file and the index files along with it.

Both classes implement same functionalities and internally handle whether the complete graph is loaded or not, the user doesn not
have to manage any memory themselves.

For examples on how to use these classes, please take a look at the next section.

# Usage and Examples
To generate the index for a GFA file, **extgfa** can be simply called from the command line after installation.
First, you need to choose which algorithm to use for chunking, there are 3 options
1. `lv` for Louvian communities Algorithm
2. `gm` for Clauset-Newman-Moore Algorithm
3. `kl` for Kernighal-Lin algorithm

Then you need to give the input GFA file, the name of the output GFA file and the upper and lower thresholds.
The thresholds are integer.

## HPRC Minigraph Chr22 Example
The following code snippet uses the graph in the example directory in this repo. This graph represent Chr22 from the 
[HPRC minigraph](https://github.com/human-pangenomics/hpp_pangenome_resources).

```
$ extgfa gm chm13-90c-chr22.gfa chm13-90c-chr22_chunked_gm.gfa 300 30
```
This means that **extgfa** will run `gm` algorithm on the input graph and a chunk can be at most 300 nodes big,
and minimum 30 nodes, if less than 30 nodes, it will be merged with neighboring chunks, if bigger than 300 nodes, it will be split further.

This will produce 4 files:
1. `chm13-90c-chr22-chunked_gm.csv` which is a Bandage compatible CSV file with colors for the different chunks for visualization
2. `chm13-90c-chr22-chunked_gm.db` which is the node_id:chunk_id database
3. `chm13-90c-chr22-chunked_gm.index` which is the pickled chunk_id:(offset, n_lines)
4. `chm13-90c-chr22-chunked_gm.gfa` is the new reordered GFA file

