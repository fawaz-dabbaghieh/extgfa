# distgfa

This is a proof of concept for an external-memory GFA representation, which allows working on the indexed GFA file
to be done with low memory.
So far two algorithms for partitioning the graph have been implemented, the Kernighan-Lin algorithm with some recursive
splitting and merging of smaller chunks in the graph. And Greedy Modularity Communities.