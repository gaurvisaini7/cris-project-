import networkx as nx

G = nx.Graph()

G.add_edge("CB-23", "SP-12")
G.add_edge("SP-12", "BM-5")

print("Nodes:", list(G.nodes()))
print("Edges:", list(G.edges()))
