# Changelog

## 26.1.0

- Improved polygon conversion reliability for SHP, KML, KMZ, and supported CAD sources.
- Refined CRS transformation and selected attribute transfer.
- Improved CAD layer mapping and output validation.
- Added sample data and clearer usage documentation.

## 26.01

- Initial QGIS edition supplied by the author.


## 26.1.0 — compatibility and reliability revision

- Do not assign the nearest outside text when a polygon contains no matching text.
- Preserve multipart polygon geometry and check memory-provider insertion results.
- Refresh source inspection when the input path changes.
- Do not use CAD EntityHandle or RefName as fallback label text.
- Protect existing SHP/KML/KMZ/DXF destinations.
