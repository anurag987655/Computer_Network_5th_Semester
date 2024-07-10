import heapq
from collections import defaultdict

def networkDelayTime(times, n, k):
    # Create an adjacency list for the graph
    graph = defaultdict(list)
    for u, v, w in times:
        graph[u].append((v, w))
    
    # Initialize the priority queue
    pq = [(0, k)]
    
    # Dictionary to store the shortest distance to each node
    dist = {i: float('inf') for i in range(1, n + 1)}
    dist[k] = 0
    
    while pq:
        current_distance, node = heapq.heappop(pq)
        
        if current_distance > dist[node]:
            continue
        
        for neighbor, weight in graph[node]:
            distance = current_distance + weight
            
            if distance < dist[neighbor]:
                dist[neighbor] = distance
                heapq.heappush(pq, (distance, neighbor))
    
    # Get the maximum distance in dist
    max_dist = max(dist.values())
    
    return max_dist if max_dist != float('inf') else -1

# Example usage
times = [[2, 1, 1], [2, 3, 1], [3, 4, 1]]
n = 4
k = 2
print(networkDelayTime(times, n, k))  # Output: 2
