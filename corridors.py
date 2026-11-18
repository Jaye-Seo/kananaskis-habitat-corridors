"""Compare resistance assumptions on a small, reproducible habitat network."""
import argparse
import csv
import heapq
import json
import math
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt, maximum_filter, minimum_filter

CELL = 25  # metres per cell in this fictional landscape
PATCHES = {"A": (48, 9), "B": (32, 119), "C": (74, 100)}
MOVES = [(dy, dx, math.hypot(dy, dx)) for dy in (-1, 0, 1)
         for dx in (-1, 0, 1) if dy or dx]


def sample_landscape():
    """Create reproducible inputs. Coordinates are local raster indices."""
    y, x = np.indices((90, 132))
    dem = (82*np.sin(x/13+y/17) + 90*np.cos(x/21-y/9)
           + 270*np.exp(-((x-62)**2/190+(y-56)**2/90)))
    road = (x > 18) & (x < 113) & (np.abs(y-(43-0.07*x+3*np.cos(x/13))) < 1.3)
    trail = (np.abs(y-(61-0.21*x+5*np.sin(x/16))) < 0.9)
    water = (np.abs(y-(24+0.19*x+7*np.sin(x/19))) < 1.3)
    return dem, road, trail, water


def factors(dem, road, trail, water):
    """Convert continuous measurements into dimensionless contributions in [0,1]."""
    rugged = maximum_filter(dem, 3) - minimum_filter(dem, 3)
    road_dist = distance_transform_edt(~road)*CELL
    trail_dist = distance_transform_edt(~trail)*CELL
    hydro_dist = distance_transform_edt(~water)*CELL
    return (np.clip(rugged/55, 0, 1), np.clip(hydro_dist/700, 0, 1),
            np.clip(1-trail_dist/280, 0, 1), np.clip(1-road_dist/380, 0, 1))


def resistance(components, road_weight):
    if not math.isfinite(road_weight) or road_weight < 0:
        raise ValueError("Road weight must be finite and non-negative.")
    terrain, hydro, trail, road = components
    return 1 + terrain + hydro + trail + road_weight*road


def shortest_paths(cost, start):
    """Dijkstra on eight neighbours with length times mean endpoint resistance."""
    h, w = cost.shape
    if not (np.isfinite(cost).all() and np.all(cost > 0)):
        raise ValueError("A finite positive cost is required in every cell.")
    dist = np.full((h,w), np.inf)
    dist[start] = 0.0
    prev = {}
    heap = [(0.0, start)]
    while heap:
        total, (y,x) = heapq.heappop(heap)
        if total > dist[y,x]:
            continue
        for dy,dx,step in MOVES:
            yy,xx = y+dy,x+dx
            if not (0 <= yy < h and 0 <= xx < w):
                continue
            edge_cost = 0.5*(cost[y,x]+cost[yy,xx])*CELL*step
            updated = total + edge_cost
            if updated < dist[yy,xx]:
                dist[yy,xx] = updated
                prev[(yy,xx)] = (y,x)
                heapq.heappush(heap, (updated,(yy,xx)))
    return dist, prev


def network(cost, patches):
    """Choose a minimum spanning tree of the pairwise least-cost connections."""
    links = []
    names = sorted(patches)
    for i, a in enumerate(names[:-1]):
        distances, prev = shortest_paths(cost, patches[a])
        for b in names[i+1:]:
            endpoint = patches[b]
            path = [endpoint]
            while path[-1] != patches[a]:
                path.append(prev[path[-1]])
            links.append((float(distances[endpoint]), a, b, path[::-1]))
    parent = {name:name for name in names}
    def root(key):
        while parent[key] != key:
            key = parent[key]
        return key
    tree = []
    for item in sorted(links):
        _, a, b, _ = item
        ra, rb = root(a), root(b)
        if ra != rb:
            parent[ra] = rb
            tree.append(item)
    return tree


def edge_lengths(tree, near_road):
    """Count shared segments once. Exposure uses mean endpoint membership."""
    unique = set()
    for _, _, _, line in tree:
        unique.update(tuple(sorted((a,b))) for a,b in zip(line,line[1:]))
    length, exposure = 0., 0.
    for a,b in sorted(unique):
        metres = CELL*math.dist(a,b)
        length += metres
        exposure += metres * (int(near_road[a]) + int(near_road[b])) / 2
    return length, exposure


def run(output, weights):
    output.mkdir(parents=True, exist_ok=True)
    terrain, roads, trails, water = sample_landscape()
    components = factors(terrain, roads, trails, water)
    near = distance_transform_edt(~roads)*CELL <= 250
    summaries, paths = [], {}
    for weight in weights:
        tree = network(resistance(components,weight), PATCHES)
        length, exposure = edge_lengths(tree,near)
        summaries.append([weight, round(length,1), round(exposure,1), len(tree)])
        paths[str(weight)] = {a+"-"+b: [[int(y),int(x)] for y,x in line] for _,a,b,line in tree}
    with (output/"metrics.csv").open("w", newline="", encoding="utf-8") as f:
        writer=csv.writer(f)
        writer.writerow(["road_weight","network_m","within_250m_of_road_m","links"])
        writer.writerows(summaries)
    (output/"paths.json").write_text(json.dumps({"cell_m": CELL,"index_order":"row,column","scenarios":paths},indent=1)+"\n")
    return summaries


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--road-weights",type=float,nargs="+",default=[1.,8.])
    ap.add_argument("--output",type=Path,default=Path("results"))
    args = ap.parse_args()
    for w,length,exposure,count in run(args.output,args.road_weights):
        print(f"Road weight {w:g} | {count} links | {length:.1f} m total | {exposure:.1f} m near roads")
