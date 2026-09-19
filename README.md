# Spatial Format Converter

Spatial Format Converter is a QGIS plugin for polygon-focused conversion among
Shapefile, KML/KMZ, and CAD data. It can transform coordinates, retain selected
attributes, map CAD layers, and copy selected CAD text into polygon attributes.

## Requirements

- QGIS 3.22 through 3.99 on Windows, Linux, or macOS.
- A GDAL/OGR build that can read the selected source format.
- Internet access is required only for license activation and verification.

DWG and DGN input is available only when the QGIS/GDAL installation provides a
compatible reader. The plugin deliberately does not advertise DWG output;
closed-boundary DXF is the portable CAD output.

## Installation

1. Download the release ZIP without extracting it.
2. In QGIS, open **Plugins > Manage and Install Plugins > Install from ZIP**.
3. Select the ZIP, install it, and enable **Spatial Format Converter**.
4. Open it from **Vector > Spatial Format Converter** or its toolbar button.

## Quick test

1. Open `sample_data/polygons.kml` as the source.
2. Click **Inspect Source** and select its polygon layer.
3. Choose an output folder and output type such as Shapefile.
4. Run the conversion and confirm that the output contains two polygons.

The `sample_data` folder also contains a small DXF drawing for checking CAD
boundary and text-layer discovery. All sample features are synthetic.

## Activation and privacy

- Product code: `SLFTCR`
- Fixed code: `PAL`
- Trial: 2 successful conversions

Trial use is recorded only after an output is created successfully. Activation
and active-license checks use QGIS' network manager and HTTPS at
`aktivasi.ruangspasial.my.id`. The request contains the product identity,
activation code, and a pseudonymous Device ID. GIS files, geometries,
attributes, and output paths are never sent to the service. Local license state
is stored in the current user's application-data directory.

## Source, help, and support

- Help: <https://aktivasi.ruangspasial.my.id/help/spatial-format-converter-qgis>
- Source: <https://github.com/purwantodwigeo10/spatial-format-converter-qgis>
- Issues: <https://github.com/purwantodwigeo10/spatial-format-converter-qgis/issues>

Copyright (C) 2026 Dwi Purwanto / Ruang Spasial. Licensed under
GPL-3.0-or-later; see `LICENSE`.
