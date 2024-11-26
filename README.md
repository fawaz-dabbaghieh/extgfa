**extgfa** is a proof-of-concept implementation of an external-memory [GFA](https://gfa-spec.github.io/GFA-spec/GFA1.html)
representation.
It provides both some sort of index, and a graph class using it
to only load smaller parts of the graph at a time
rather than the complete graph in memory.
This is especially useful when the user only wants to look at or extract a small part of it.
The user doesn’t need to care about how the class internally deals with loading and unloading parts of the graph:
this is done seamlessly behind the scenes.

- [Idea](#idea)
- [Graph Partitioning](#graph-partitioning)
- [Graph Class](#graph-class)
- [Usage and Examples](#usage-and-examples)
    + [HPRC Minigraph Chr22 Example](#hprc-minigraph-chr22-example)
    + [Working with Graph Classes](#working-with-graph-classes)
      + [Example Algorithm using ChGraph Class](#example-algorithm-using-chgraph-class)

# Idea
The idea here is inspired by [Minecraft](https://minecraft.fandom.com/wiki/Minecraft_Wiki).
The map is partitioned into [chunks](https://minecraft.fandom.com/wiki/Chunk)
of 16x16 blocks, and chunks are stored on disk.
At any one point, only chunks close to the player's location are loaded into memory.
When the player moves in a certain direction, chunks located farther away are unloaded,
and those closer by are loaded.

This is illustrated in the figure below.
The player is located in the chunk in green,
which is loaded completely into memory along with any other associated data.
The chunks in red are the furthest away from the player and can remain unloaded.
Minecraft implements two types of intermediary chunk-loading levels, here in yellow and orange,
where only some resources are loaded: for example, textures are loaded for both levels,
but animal characters are only loaded in the yellow level closer to the player.

<p align="center">
    <img src="figures/minecraft_map_chunks.png" alt="drawing" width="300"/>
</p>

In the genome graph world,
one of the current problems with processing big graphs in the GFA format is that it is necessary to read
the entire file.
Libraries using it tend to load the entire graph in memory.
Depending on the application, this might not be necessary.
For example, if the user would like to only look at or investigate only a small part of the graph,
even just few nodes, they still need to read and load the entire GFA file
into memory, which can be quite resource-heavy.

Following the logic in Minecraft, we investigated whether a similar mechanism could be used for genome graphs in GFA format.
In other words, the graph is split into smaller connected neighborhoods (chunks), and stored in a way such that
they may be loaded on-demand and only when needed.
The following section explains how to achieve this.


# Graph Partitioning
The graph first needs to be cut into smaller neighborhoods,
then stored on disk in a format convenient for quick retrieval.
This is achieved by partitioning the graph into chunks and outputting a reordered and indexed GFA file.

There are many graph partitioning algorithms that cut the graph into smaller parts, or find connected neighborhoods. We tested three
of the algorithms implemented in the `NetworkX` Python library: the Kernighan-Lin algorithm, Louvian communities,
and Clauset-Newman-Moore greedy modularity maximization.
After testing on real-world data,
we found that Kernighan-Lin doesn’t work as well as the other two,
but all 3 are selectable in the implementation.

[//]: # (I'd put any usage information after the description/discussion of the algorithm -K)

Two thresholds are defined:
- Top: maximum number of nodes in a chunk, i.e., if a chunk
has more nodes than this, it will be split further with the chosen algorithm.
- Bottom: minimum number of nodes in a chunk, i.e., if a chunk has fewer nodes than this, it
will be merged with a neighboring chunk if available.

Once the graph is partitioned into chunks, each chunk is assigned an ID arbitrarily from 0 to _N_ where _N_ is the number of chunks.

Finally, 3 files are produced:

1. Reordered GFA file: **extgfa** produces a new GFA file based on the input,
but where the S and L lines are ordered in a way such that nodes and edges belonging to the same chunk are written consecutively.
2. Chunk offset index: this is simply a `pickled` dictionary where the key is the integer chunk ID, and the value is a tuple of the offset number in the reordered GFA output, and the number of lines to read starting from that offset.
By keeping track of each chunk's file offset in the output GFA file and the number of lines for that chunk,
we can retrieve a chunk without having to read the entire file
by only jumping to its specific file offset then reading its specific number of lines.
3. `dbm` file written using `shelve`: A key-value external database where the key is the node ID and the value is the chunk ID.
This database is used to figure out which chunk to load when encountering a node that is not loaded yet.
It is not loaded into memory.

Thus, **extgfa** takes a GFA graph as input and produces three files as output: a reordered GFA, a pickled index, and the `dbm` database.


<p align="center">
    <img src="figures/distgfa_pipeline_v3.png" alt="drawing" width="800"/>
</p>

# Installation
**extgfa** is a simple Python package that can be installed with `python3 setup.py install` or from the package directory by running
`pip install .`.

Once installed, it can be used as a command line tool for creating the chunked graph,
but also within a Python program by importing the implemented graph classes with
`from extgfa.Graph import Graph` or `from extgfa.ChGraph import ChGraph`.

# Graph Class
Two GFA graph classes are implemented and available to use in **extgfa**:
- `extgfa.Graph`: this class accepts any GFA file and loads it completely.
- `extgfa.ChGraph`: this is used for the chunked graphs, and requires the reordered GFA and index files as described above.

Both classes implement the same functionalities and internally handle whether the complete graph is loaded or not,
i.e., the user doesn’t have to manage any memory themselves.

The following section provides examples on how to use them.

# Usage and Examples
To generate the index for a GFA file, **extgfa** can be simply called from the command line after installation.
First, you need to choose the algorithm to use for chunking among three options:
1. `lv` for the Louvian communities algorithm
2. `gm` for the Clauset-Newman-Moore algorithm
3. `kl` for the Kernighal-Lin algorithm

Then you need to specify the path of the input GFA file,
the path of the output GFA file and the top and bottom thresholds as integers.

## HPRC Minigraph Chr22 Example
The example uses the graph in this repository's **example** directory.
It represents Chromosome 22 from the 
[HPRC minigraph](https://github.com/human-pangenomics/hpp_pangenome_resources) resource.

```
$ extgfa gm chm13-90c-chr22.gfa chm13-90c-chr22-chunked_gm.gfa 300 30
```
Using this, **extgfa** will run the `gm` algorithm on the input graph
with chunks of at least 30 and at most 300 nodes.
Smaller chunks will be merged with neighboring ones,
and bigger chunks will be split further.

This will produce 4 files:
1. `chm13-90c-chr22-chunked_gm.csv`, a [Bandage](https://rrwick.github.io/Bandage/) compatible CSV file with colors for the different chunks, for visualization. Please note that there is a limited number of colors, therefore, different chunks might be colored the same if there are many chunks, but this CSV can still help visualizing small graphs with few chunks.
2. `chm13-90c-chr22-chunked_gm.db`, the `node_id:chunk_id` database
3. `chm13-90c-chr22-chunked_gm.index`, the pickled `chunk_id:(offset, n_lines)`
4. `chm13-90c-chr22-chunked_gm.gfa`, the new reordered GFA file

The `ChGraph` class can now be used to work with this graph with minimal memory usage.
For instance, if we want to extract a small subgraph around a given node, we can use
the already-implemented breadth-first search (BFS) function by giving it a start node,
and saving it as a separate GFA file:

```python
from extgfa.ChGraph import ChGraph

graph = ChGraph("chm13-90c-chr22-chunked_gm.gfa")
# the length of the graph is 0: no nodes have been loaded yet
print(len(graph))
# 0

# now we want to extract a neighborhood of 50 nodes around the node s594053: we
# can use the bfs function implemented in the graph class, which returns a set
# of node IDs that represent this neighborhood. even though the graph is empty,
# internally it will automatically load the necessary chunks
subgraph = graph.bfs("s594053", 50)

# to output this subgraph into a new GFA, call the write_graph method with the
# set of nodes and an output file name; use append=True to append to an 
# already existing output GFA file
graph.write_gfa(set_of_nodes=subgraph, output_file="test_subgraph.gfa", append=False)

# note: this works in exactly the same way when using the Graph class instead
# of ChGraph: both have the same functionalities and are named the same
```

**PLEASE NOTE** that the reordered GFA and indexes are **immutable**.
In other words, the `ChGraph` does not explicitly disallow modifications to the graph object loaded in Python. However, any modifications will not be written to the index files and the reordered GFA file. You can then use the `write_gfa` function to output the graph after modification if needed. Make sure to not edit the index files or the output GFA file manually to not invalidate the offsets.

## Working with the Graph classes
The following code showcases the classes' API which enables the user
to implement their own graph algorithms and applications on top.

```python
from extgfa.ChGraph import ChGraph

graph = ChGraph("chm13-90c-chr22-chunked_gm.gfa")

# to get the chunk ID from a node ID that is not yet loaded
# (node ids are always strings):
chunk_id = graph.get_node_chunk("s287613")

# chunks may be loaded manually:
graph.load_chunk(chunk_id)

# there is a limit to how many chunks are kept in memory before older ones are
# purged, by default 10. it is configurable: increasing it will in turn
# increase the maximal number of chunks allowed in memory, hence increasing
# the memory requirements, but also increasing node access speed
print(graph.loaded_c_limit)
graph.loaded_c_limit = 20

# to show how many chunks are loaded:
len(graph.loaded_c)

# to get the neighbors of a node:
neighbors = graph.neighbors("s287613")
# this returns a list of node IDs for all nodes that share an edge with this
# one, and also automatically loads each missing chunk if those nodes are not
# yet loaded

# because GFAs represent bidirected graphs, nodes have a start and an end
# and can be accessed from either direction, i.e. two nodes may be connected
# to either node's start or end. the edge set returned is therefore a set of
# 3-tuples (node_id, direction, overlap), where direction denotes to which
# "side" of the neighboring node an edge connects: 0 for start, 1 for end:
from_start_edges = graph["s287613"].start
# {('s287612', 1, 0), ('s577859', 0, 0)}
# thus node s287613's start is connected to s287612's end and s577859's start.

from_end_edges = graph["s287613"].end
# {('s287614', 0, 0), ('s650547', 0, 0)}
# here s287613's end is connected to s287614's start and to s650547's end.
# both edges have an overlap of 0
```

### Example Algorithm using ChGraph Class
As an additional example, let's say the user wants to implement depth-first search (DFS) using the
chunked graph class.
The following code shows how:

```python
from extgfa.ChGraph import ChGraph

def dfs(graph, start, cutoff):
    visited = set()
    stack = [start]
    while stack:
        node = stack.pop()
        if node not in visited:
            visited.add(node)
            if len(visited) > cutoff:
              return visited

            for neighbor in graph.neighbors(node):
                if neighbor not in visited:
                    stack.append(neighbor)
    return visited

# load the chunked graph
graph = ChGraph("chm13-90c-chr22-chunked_gm.gfa")

# call the dfs function on the currently "empty" graph: the class will
# transparently load any needed chunks without the user's intervention
dfs_list = dfs(graph, "s578029", 100)

```

### Extracting GFA Paths
The user can also use `check_path` and `extract_path_seq` of the classes to check if a certain path exists,
and extract the sequence of the path.
The following code snippet shows this:

```python
from extgfa.ChGraph import ChGraph

graph = ChGraph("chm13-90c-chr22-chunked_gm.gfa")

path = ">s588888>s288175>s656033"

# this returns the sequence of the path as a string
path_seq = graph.extract_path_seq(path)

```

**NOTE**: This only works for paths without overlaps, so it will concatenate the sequences of the nodes in the path
with respect to their directions, but will not take the overlap into consideration for now.
