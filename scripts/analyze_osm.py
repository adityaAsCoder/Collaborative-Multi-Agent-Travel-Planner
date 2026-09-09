import fiona
import json

def analyze_osm():
    gpkg = 'datasets/osm/northern-zone.gpkg'
    try:
        layers = fiona.listlayers(gpkg)
        if 'gis_osm_roads_free' in layers:
            with fiona.open(gpkg, layer='gis_osm_roads_free') as src:
                bounds = src.bounds
                print(f"OSM Roads Bounds: {bounds}")
                print(f"CRS: {src.crs}")
                # We can't load the whole 1GB layer quickly in fiona, but bounds gives bbox
    except Exception as e:
        print(f"OSM Read Error: {e}")

if __name__ == '__main__':
    analyze_osm()
