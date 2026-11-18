"""ArcGIS Pro Python entry point for user-supplied, projected Kananaskis-style layers."""
import argparse
import math
from pathlib import Path


def run(args):
    import arcpy
    from arcpy.sa import (Abs, Con, DistanceAccumulation, FocalStatistics,
                          NbrRectangle, OptimalRegionConnections, Raster)
    if not math.isfinite(args.road_weight) or args.road_weight < 0:
        raise ValueError("Road weight must be finite and non-negative.")
    for name in ("dem", "roads", "trails", "water", "patches", "boundary", "output"):
        setattr(args, name, str(Path(getattr(args, name)).resolve()))
    datasets = [args.dem,args.roads,args.trails,args.water,args.patches,args.boundary]
    refs = [arcpy.Describe(ds).spatialReference for ds in datasets]
    if not all(sr.type=="Projected" and abs(sr.metersPerUnit-1) < 1e-8 for sr in refs):
        raise ValueError("All input layers must use a projected CRS in metres.")
    if any(ref.name != refs[0].name for ref in refs):
        raise ValueError("Project the inputs into the same CRS first.")
    if arcpy.CheckExtension("Spatial") != "Available":
        raise RuntimeError("The Spatial Analyst license is unavailable.")
    if arcpy.Exists(args.output):
        raise ValueError("Choose a new output geodatabase so a previous run is preserved.")
    arcpy.CheckOutExtension("Spatial")
    try:
        dest = Path(args.output)
        arcpy.management.CreateFileGDB(str(dest.parent),dest.name)
        with arcpy.EnvManager(workspace=str(dest),scratchWorkspace=str(dest),extent=args.boundary,
                              mask=args.boundary,snapRaster=args.dem,cellSize=25,outputCoordinateSystem=refs[0]):
            def cap(raster):
                return Con(raster > 1, 1, raster)
            rough = FocalStatistics(Raster(args.dem),NbrRectangle(3,3,"CELL"),"RANGE","DATA")
            rugged = cap(Abs(rough)/55.)
            hydro = cap(DistanceAccumulation(args.water)/700.)
            trail = 1 - cap(DistanceAccumulation(args.trails)/280.)
            road = 1 - cap(DistanceAccumulation(args.roads)/380.)
            cost = 1 + rugged + hydro + trail + args.road_weight*road
            surface = str(dest/"resistance")
            cost.save(surface)
            OptimalRegionConnections(args.patches,str(dest/"corridors"),None,surface)
    finally:
        arcpy.CheckInExtension("Spatial")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("dem","roads","trails","water","patches","boundary","output"):
        p.add_argument("--"+name,required=True)
    p.add_argument("--road-weight",type=float,default=1.)
    run(p.parse_args())
