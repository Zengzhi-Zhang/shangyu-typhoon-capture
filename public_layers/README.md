# Public cartographic layers

These assets contain public geographic data only. No sensor identifiers, vehicle identifiers, management-unit attributes or private positions are included. GeoJSON files are WGS84 geometry-only FeatureCollections with empty properties and no feature IDs, clipped to the figure frames. Public terrain TIFFs preserve the original rendered RGB array values losslessly; their projected frame extents are documented separately.

- OpenStreetMap district/province boundaries and major-road geometry: copyright OpenStreetMap contributors, ODbL. https://www.openstreetmap.org/copyright . Derived public geometry remains under ODbL.
- Natural Earth land/coastline polygons: public domain. https://www.naturalearthdata.com/about/terms-of-use/ .
- IBTrACS western-Pacific In-Fa/CMA track and interpolated public landfall positions remain in the published source CSVs. Cite Gahtan et al. (2024), IBTrACS v4r01, DOI10.25921/82ty-9e16, and Knapp et al. (2010). https://www.ncei.noaa.gov/products/international-best-track-archive .
- Terrain hillshade: derived from AWS Terrain Tiles, with USGS GMTED2010/SRTM and NOAA ETOPO1 attribution. https://registry.opendata.aws/terrain-tiles/ ; https://github.com/tilezen/joerd/blob/master/docs/attribution.md . Only cropped figure hillshades are distributed, not a global tile database.

See asset_licenses.json for exact file hashes and per-asset attribution. terrain_manifest.json describes projected raster extents. The precise public Baiguan town-centre constant in the drawing helper is an OpenStreetMap landmark; camera and taxi plotting cells remain rounded to0.01degrees in the source data.
