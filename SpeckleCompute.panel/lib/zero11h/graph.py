#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Base concept from John Guttag - Introduction to Computation and Programming
# Simple pure Python graph class

class Node(object):
    def __init__(self, eid):
        self.eid = eid  # Revit id as integer

    def __eq__(self, other):
        return self.eid == other.eid

    def __str__(self):
        return str(self.eid)

    def __repr__(self):
        return str(self.eid)

    def __hash__(self):
        return self.eid


class Edge(object):
    def __init__(self, src_node, dest_node):
        self.src = src_node
        self.dest = dest_node

    def __repr__(self):
        return str(self.src) + '->' + str(self.dest)


class Graph(object):
    """
    Undirected graph

    """
    def __init__(self):
        self.nodes = []
        self.edges = {}

    def add_node(self, node):
        if node in self.nodes:
            print('Duplicate node {} already in graph'.format(node.eid))
        else:
            self.nodes.append(node)
            # self.edges[node] = []

    def add_edge(self, edge):
        if not edge.src in self.nodes:
            self.add_node(edge.src)
        elif not edge.dest in self.nodes:
            self.add_node(edge.dest)

        if not self.edges.get(edge.src):
            self.edges[edge.src] = set([edge.dest])
        if not self.edges.get(edge.dest):
            self.edges[edge.dest] = set([edge.src])
        if self.edges.get(edge.src):
            self.edges[edge.src].add(edge.dest)
        if self.edges.get(edge.dest):
            self.edges[edge.dest].add(edge.src)

    def get_parents_of(self, node):
        parents = set()
        for parent, node_list in self.edges.items():
            if node in node_list:
                parents.add(parent)
        return parents

    def get_children_of(self, node):
        return self.edges.get(node, [])

    def has_node(self, node):
        return node in self.nodes

    @property
    def all_edges(self):
        edges = []
        for node in self.nodes:
            edges.extend(self.get_children_of(node))
        return edges

    def __repr__(self):
        result = ''
        for src in self.nodes:
            for dest in self.edges[src]:
                result = '{}{} -> {}\n'.format(result,
                                               src.eid,
                                               dest.eid)
        return result[:-1]


if __name__ == "__main__":
    g = Graph()
    print(g.edges)
    nodes = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

    #[g.add_node(Node(node)) for node in nodes]
    #edges = [[3,1, False],[2,1, False],[1,4, True],[5,4, False], [4,7,True], [1,8,True]]
    #edges = [[3, 1, False], [2, 1, False], [1, 4, False], [5, 4, False], [4, 7, False], [1, 8, False]]
    #edges.extend([[9,6,False],[10,6,False]])
    edges = [[3, 1, False]]
    edges.extend([[2, 1, False]])
    edges.extend([[1, 4, False]])
    #edges = [[3, 1, False], [2, 1, False], [1, 4, False]]
    #[g.add_edge(Edge(Node(src), Node(dest)), simmetrical=simm) for src, dest, simm in edges]
    [g.add_edge(Edge(Node(src), Node(dest))) for src, dest, _ in edges]
    print(g)
    print(g.get_parents_of(Node(1)))
    print(g.get_children_of(Node(1)))
