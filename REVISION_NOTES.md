# Revision notes — spatial_format_converter_qgis 26.1.0

Version retained at the author's request.

## Changes

- Scope QGIS geometry enums through `QgsWkbTypes.GeometryType` to clear the remaining Qt6/QGIS API scanner findings.

- Use scoped Qt enums, exec(), Qt-compatible QAction imports and explicit Qt5/Qt6 field types.
- Use bounded License Hub HTTPS requests, manual redirect policy, HTTP/network error checks and an already-finished reply guard.
- Give explicit inactive/revoked/expired/pending states priority over conflicting success flags.
- Prevent reentrant Run operations during nested event loops.
- Require new output filenames to protect existing data; partial new output may remain if a later write fails.
- Do not assign the nearest outside text when a polygon contains no matching text.
- Preserve multipart polygon geometry and check memory-provider insertion results.
- Refresh source inspection when the input path changes.
- Do not use CAD EntityHandle or RefName as fallback label text.
- Protect existing SHP/KML/KMZ/DXF destinations.

## Required QGIS test

Test sample KML to SHP and SHP to KML/KMZ. Test multipart polygons and compare feature counts. For CAD text, leave one polygon without an internal label: its attribute must stay empty even when a neighbouring label exists. Test DXF output in AutoCAD.

## Validation limits

Offline regression tests, actual standalone PyQt5/PyQt6 enum checks, and Python lint/syntax checks were run. Full QGIS/GDAL processing, Windows file locking, live activation and the official repository scanners were not run. The package retains QGIS 3.22–3.99 compatibility metadata; no QGIS 4 support is claimed. Standalone Qt tests do not establish complete QGIS compatibility.

## Publishing

Install this ZIP in QGIS without extracting it. For GitHub, extract and upload the contents of this plugin folder at the existing repository root. Do not upload another plugin's files. Check public repository, issue tracker and help URLs before uploading to QGIS. Changing GitHub source or version text does not replace the ZIP stored on the QGIS plugin site. If the version already exists, inspect its Manage/Edit options before replacing it; do not delete the whole plugin.
