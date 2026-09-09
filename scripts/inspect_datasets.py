import os
import json
import pandas as pd
import geopandas as gpd

def inspect_datasets():
    os.makedirs('reports/data_inspection', exist_ok=True)
    with open('reports/data_inspection/dataset_audit.md', 'w', encoding='utf-8') as f:
        f.write("# Dataset Audit Report\n\n")

        f.write("## 1. Tourism Dataset\n\n")
        try:
            with open('datasets/raw/tourism/dataset_schema.json', 'r') as schema_f:
                schema = json.load(schema_f)
                f.write(f"Schema details: {json.dumps(schema, indent=2)}\n\n")
        except Exception as e:
            f.write(f"Error reading schema: {e}\n\n")
            
        try:
            with open('datasets/raw/tourism/india_tourism_dataset.json', 'r', encoding='utf-8') as data_f:
                data = json.load(data_f)
                f.write(f"Total Rows: {len(data)}\n")
                if len(data) > 0:
                    f.write(f"Fields available: {list(data[0].keys())}\n")
        except Exception as e:
            f.write(f"Error reading dataset: {e}\n\n")

        f.write("\n## 2. Hotels Datasets\n\n")
        hotel_files = ['datasets/raw/hotels/hotels.csv', 'datasets/raw/hotels/OYO_HOTEL_ROOMS.csv', 'datasets/raw/hotels/OYO_HOTEL_ROOMS.xlsx']
        for file in hotel_files:
            try:
                if file.endswith('.csv'):
                    df = pd.read_csv(file)
                else:
                    df = pd.read_excel(file)
                f.write(f"### {os.path.basename(file)}\n")
                f.write(f"- Rows: {len(df)}\n")
                f.write(f"- Columns: {list(df.columns)}\n")
                f.write(f"- Missing values:\n{df.isnull().sum().to_string()}\n")
            except Exception as e:
                f.write(f"Error reading {file}: {e}\n\n")
                
        f.write("\n## 3. OSM Data\n\n")
        try:
            gpkg = 'datasets/osm/northern-zone.gpkg'
            f.write(f"File size: {os.path.getsize(gpkg)} bytes\n")
            # fiona could read layers
            import fiona
            layers = fiona.listlayers(gpkg)
            f.write(f"Layers: {layers}\n")
        except Exception as e:
            f.write(f"Error reading OSM gpkg: {e}\n\n")

if __name__ == '__main__':
    inspect_datasets()
