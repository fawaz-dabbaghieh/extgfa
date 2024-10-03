import pdb


def b_is_simple(bubble):
    if len(bubble['inside']) == 2:
        return True
    return False


def b_is_super(bubble):
    if len(bubble['inside']) > 2:
        return True
    return False


def find_sb_alg(graph, s, direction, only_simple=False, only_super=False):
    """
    takes the graph and a start node s and add a bubble to the chain 
    if one is found if s was the source
    """
    # I tuples of node ids and the direction
    seen = set()
    visited = set()
    nodes_inside = []
    seen.add((s.id, direction))
    # seen.add(s.id)
    S = {(s, direction)}
    while len(S) > 0:

        v = S.pop()
        v = (v[0], v[1])
        visited.add(v[0].id)

        nodes_inside.append(v[0])

        # it's visited so it's not in the seen list anymore
        seen.remove((v[0].id, v[1]))

        # from which direction we are going we take those children
        if v[1] == 0:
            # print("here1")
            # pdb.set_trace()
            children = graph.children(v[0].id, 0)
            # children = v[0].start
        else:
            # print("here2")
            children = graph.children(v[0].id, 1)
            # children = v[0].end

        if len(children) == 0:
            # it's a tip
            break

        for u in children:
            # check where we entered to get children from the other side
            if u[1] == 0:
                u_child_direction = 1
                # u_parents = [x[0] for x in graph.nodes[u[0]].start]
                # try:
                u_parents = graph.children(u[0], 0)
                # except:
                #     pdb.set_trace()
                u_parents = [x[0] for x in u_parents]

            else:
                u_child_direction = 0
                # u_parents = [x[0] for x in graph.nodes[u[0]].end]
                u_parents = graph.children(u[0], 1)
                u_parents = [x[0] for x in u_parents]

            if u[0] == s.id:
                # we are in a loop
                S = set()  # so I exit the outer loop too
                break

            # adding child to seen
            # seen.add(u[0])
            if u[1] == 0:
                seen.add((u[0], 1))
            else:
                seen.add((u[0], 0))
            # if all u_parents are visited then we push it into S
            if all(graph.nodes[i].id in visited for i in u_parents):
                S.add((graph.nodes[u[0]], u_child_direction))

        # checking if we finished
        if (len(S) == 1) and (len(seen) == 1):
            t = S.pop()
            # I was adding t[0] then removing it again
            # not sure why so I commented this out just in case I missed something
            # nodes_inside.append(t[0])

            # this was 2 instead of 1 because t[0] was also added to inside
            if len(nodes_inside) == 1:
                # it's an empty bubble
                # this shouldn't happen if the graph is compacted
                break

            # t[0].visited = True

            # because I'm looking in both directions I end up finding each
            # bubble twice, so I can hash the id of source and sink
            # and see if I've already found it or not
            nodes_inside.remove(s)
            # nodes_inside.remove(t[0])
            # bubble = Bubble(source=s, sink=t[0], inside=nodes_inside)
            bubble = {"source":s.id, "sink":t[0].id, "inside":[n.id for n in nodes_inside]}

            if only_simple:
                if b_is_simple(bubble):
                    return bubble
            elif only_super:
                if b_is_super(bubble):
                    return bubble
            else:
                return bubble

    return None