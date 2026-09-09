# Data Strategy & Architecture

## Overview
This document outlines the data strategy for the Collaborative Multi-Agent Optimization for Personalized Travel Planning project.

## Provenance
- `northern-zone.gpkg`: OpenStreetMap dataset for routing.
- `india_tourism_dataset.json`: Tourist destination data with categories and scores.
- `OYO_HOTEL_ROOMS.csv / .xlsx`: Hotel names, locations, prices, and ratings.

## Missing Data
- `attractions/` folder is empty. We need a dataset containing specific attraction locations, costs, visit durations, and popularity.
- Only a few explicit coordinates for hotels exist and would require additional cleaning.

## Dataset Coverage
- **Destinations**: The tourism dataset has 100 entries, but destinations from the hotel list are more numerous. We need an intersection table indicating full coverage before routing.
- **Attractions**: None available in raw dataset; primary attractions are listed only as strings in the tourism dataset.
- **Hotels**: 791 records but no explicit coordinates (only 'Location' string which needs geocoding).
- **Transport**: OSM covers the northern zone, but we lack processed graph distances.

## Data Pipeline
1. Inspect -> `data_pipeline/inspect.py`
2. Validate (Pydantic constraints built-in)
3. Load into SQLite -> `app/data/models.py`
