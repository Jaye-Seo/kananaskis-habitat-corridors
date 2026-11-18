import math
import unittest
import numpy as np
from corridors import CELL, edge_lengths, network, resistance, shortest_paths

class TestCorridors(unittest.TestCase):
    def test_diagonal(self):
        dist, _ = shortest_paths(np.ones((3,3)), (0,0))
        self.assertAlmostEqual(dist[2,2], 2*math.sqrt(2)*CELL)
    def test_shared_edges_count_once(self):
        t = [(0,"a","b",[(0,0),(0,1),(0,2)]),(0,"a","c",[(0,0),(0,1),(1,1)])]
        self.assertEqual(edge_lengths(t,np.ones((2,3),dtype=bool)),(75.,75.))
    def test_high_resistance_avoided(self):
        g = np.ones((5,7)); g[2,2:5]=80
        t = network(g,{"a":(2,0),"b":(2,6),"c":(4,6)})
        self.assertEqual(len(t),2)
        self.assertTrue(all(g[cell] < 80 for *_,path in t for cell in path))
    def test_bad_weights(self):
        with self.assertRaises(ValueError): resistance((1,1,1,1),float("nan"))

if __name__=="__main__":unittest.main()
