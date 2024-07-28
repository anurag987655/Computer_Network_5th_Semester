def print_solution(dist):
    print("Vertex Distance from Source")
    for key, value in dist.items():
        print('  ' + key, ' :    ', value)


class Graph:

    def __init__(self, vertices):
        self.V = vertices   
        self.graph = []     
        self.nodes = []

    def add_edge(self, s, d, w):
        self.graph.append([s, d, w])
    
    def add_node(self, value):
        self.nodes.append(value)

    def bellman_ford(self, src):
        dist = {i: float("Inf") for i in self.nodes}
        dist[src] = 0

        for _ in range(self.V-1):
            for s, d, w in self.graph:
                if dist[s] != float("Inf") and dist[s] + w < dist[d]:
                    dist[d] = dist[s] + w
        
        for s, d, w in self.graph:
            if dist[s] != float("Inf") and dist[s] + w < dist[d]:
                print("Graph contains negative cycle")
                return
        print_solution(dist)


g = Graph(7)
g.add_node("A")
g.add_node("B")
g.add_node("C")
g.add_node("D")
g.add_node("E")
g.add_node("F")
g.add_node("G")
g.add_edge("A", "B", 6)
g.add_edge("A", "C", 4)
g.add_edge("A", "D", 5)
g.add_edge("B", "E", -1)
g.add_edge("C", "E", 3)
g.add_edge("C", "B", -2)
g.add_edge("D", "C", -2)
g.add_edge("D", "F", -1)
g.add_edge("E", "G", 3)
g.add_edge("F", "G", 3)
g.bellman_ford("A")


        

  
