from collections import defaultdict


class Graph:
    def __init__(self):
        self.nodes = set()
        self.edges = defaultdict(list)
        self.distances = {}

    def add_node(self, value):
        self.nodes.add(value)

    def add_edge(self, from_node, to_node, distance):
        self.edges[from_node].append(to_node)
        self.distances[(from_node, to_node)] = distance


def dijkstra(graph, initial):
    visited = {initial: 0}
    path = defaultdict(list)

    nodes = set(graph.nodes)

    while nodes:
        min_node = None
        for node in nodes:
            if node in visited:
                if min_node is None:
                    min_node = node
                elif visited[node] < visited[min_node]:
                    min_node = node
        if min_node is None:
            break

        nodes.remove(min_node)
        current_weight = visited[min_node]

        for edge in graph.edges[min_node]:
            weight = current_weight + graph.distances[(min_node, edge)]
            if edge not in visited or weight < visited[edge]:
                visited[edge] = weight
                path[edge].append(min_node)

    return visited, path


custom_graph = Graph()
custom_graph.add_node("A")
custom_graph.add_node("B")
custom_graph.add_node("C")
custom_graph.add_node("D")
custom_graph.add_node("E")
custom_graph.add_node("F")

custom_graph.add_edge("A", "B", 5)
custom_graph.add_edge("A", "C", 2)
custom_graph.add_edge("B", "D", 1)
custom_graph.add_edge("B", "E", 7)
custom_graph.add_edge("B", "F", 9)
custom_graph.add_edge("C", "D", 4)
custom_graph.add_edge("C", "B", 2)
custom_graph.add_edge("D", "E", 5)
custom_graph.add_edge("E", "F", 2)

print(dijkstra(custom_graph, "A"))
