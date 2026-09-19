# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import re
import tempfile
import zipfile
from dataclasses import dataclass

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsProject,
    QgsProviderRegistry,
    QgsSpatialIndex,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant


TECHNICAL_FIELDS = {
    "fid", "objectid", "oid", "shape", "shape_length", "shape_area",
    "length", "area", "perimeter", "style", "ogr_style", "entityhandle",
    "docname", "docpath", "doctype", "docver", "blkcolor", "blklinetype",
    "blklinewt", "color", "linetype", "linewt", "refname",
}
LAYER_FIELD_CANDIDATES = ("Layer", "layer", "LAYER", "LayerName", "layer_name")
TEXT_FIELD_CANDIDATES = (
    "Text", "TEXT", "TextString", "text_string", "TextValue", "text_value",
    "Label", "LABEL", "Name", "NAME", "RefName", "EntityHandle",
)


class ConversionError(RuntimeError):
    pass


@dataclass
class SourcePart:
    name: str
    uri: str
    layer: QgsVectorLayer


def detect_format(path):
    extension = os.path.splitext(path)[1].lower()
    if extension == ".shp":
        return "SHP"
    if extension in (".kml", ".kmz"):
        return "KML"
    if extension in (".dwg", ".dxf", ".dgn"):
        return "CAD"
    raise ConversionError(
        "Unsupported source format: {}".format(extension or "unknown"))


def _field_lookup(layer):
    return {field.name().lower(): field.name() for field in layer.fields()}


def find_field(layer, candidates):
    lookup = _field_lookup(layer)
    for candidate in candidates:
        if candidate.lower() in lookup:
            return lookup[candidate.lower()]
    return ""


def semantic_fields(layer):
    values = []
    for field in layer.fields():
        name = field.name()
        if name.lower() in TECHNICAL_FIELDS:
            continue
        values.append(name)
    return values


def safe_name(value, used=None, shapefile=False, force_sfc=False):
    used = used if used is not None else set()
    value = str(value or "field").strip()
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", value)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_") or "field"
    if force_sfc or cleaned[0].isdigit():
        cleaned = "SFC" + cleaned
    if shapefile:
        cleaned = cleaned[:10]
    base = cleaned
    number = 1
    while cleaned.lower() in used:
        suffix = str(number)
        limit = 10 if shapefile else 63
        cleaned = base[: max(1, limit - len(suffix))] + suffix
        number += 1
    used.add(cleaned.lower())
    return cleaned


def safe_cad_layer(value, fallback="SFC_POLYGON"):
    value = re.sub(r"[<>/\\\":;?*|=,]", "_", str(value or "").strip())
    value = re.sub(r"\s+", "_", value).strip("_.")
    return (value or fallback)[:255]


class ConversionEngine:
    def __init__(self, log=None):
        self.log = log or (lambda _message: None)
        self.path = ""
        self.source_format = ""
        self.parts = []
        self.layer_values = []
        self.attribute_layer_values = []
        self.layer_field = ""

    def _message(self, text):
        self.log(str(text))

    def inspect(self, path):
        if not path or not os.path.isfile(path):
            raise ConversionError("Source file was not found.")
        self.path = os.path.abspath(path)
        self.source_format = detect_format(self.path)
        self.parts = self._load_parts(self.path)
        if not self.parts:
            raise ConversionError(
                "QGIS could not read a compatible vector layer from the source.")

        self.layer_field = ""
        self.layer_values = []
        self.attribute_layer_values = []
        if self.source_format == "CAD":
            all_values = set()
            boundary_values = set()
            for part in self.parts:
                layer_field = find_field(part.layer, LAYER_FIELD_CANDIDATES)
                if not layer_field:
                    continue
                values = {
                    str(value)
                    for value in part.layer.uniqueValues(part.layer.fields().indexOf(layer_field))
                    if value not in (None, "")
                }
                if values:
                    self.layer_field = layer_field
                    all_values.update(values)
                    if QgsWkbTypes.geometryType(part.layer.wkbType()) in (
                        QgsWkbTypes.LineGeometry,
                        QgsWkbTypes.PolygonGeometry,
                    ):
                        boundary_values.update(values)
            self.layer_values = sorted(
                boundary_values or all_values, key=str.lower)
            self.attribute_layer_values = sorted(all_values, key=str.lower)

        if self.layer_values:
            main_choices = list(self.layer_values)
            attribute_choices = list(
                self.attribute_layer_values or self.layer_values)
        else:
            main_choices = [part.name for part in self.parts]
            attribute_choices = sorted(
                {name for part in self.parts for name in semantic_fields(
                    part.layer)},
                key=str.lower,
            )
        return {
            "format": self.source_format,
            "main_choices": main_choices,
            "attribute_choices": attribute_choices,
            "source_crs": self.parts[0].layer.crs(),
        }

    def _load_parts(self, path):
        parts = []
        seen = set()
        try:
            details = QgsProviderRegistry.instance().querySublayers(path)
        except Exception:
            details = []
        for index, detail in enumerate(details or []):
            try:
                uri = detail.uri()
                name = detail.name() or "Layer_{}".format(index + 1)
            except (AttributeError, RuntimeError) as error:
                self._message("Skipped unreadable sublayer: {}".format(error))
                uri = ""
                name = ""
            if not uri:
                continue
            if uri in seen:
                continue
            layer = QgsVectorLayer(uri, name, "ogr")
            if layer.isValid() and layer.featureCount() >= 0:
                parts.append(SourcePart(name=name, uri=uri, layer=layer))
                seen.add(uri)
        if not parts:
            name = os.path.splitext(os.path.basename(path))[0]
            layer = QgsVectorLayer(path, name, "ogr")
            if layer.isValid():
                parts.append(SourcePart(name=name, uri=path, layer=layer))
        return parts

    def _main_part(self, main_choice):
        if self.layer_values:
            for part in self.parts:
                field_name = find_field(part.layer, LAYER_FIELD_CANDIDATES)
                if not field_name:
                    continue
                if QgsWkbTypes.geometryType(part.layer.wkbType()) not in (
                    QgsWkbTypes.LineGeometry,
                    QgsWkbTypes.PolygonGeometry,
                ):
                    continue
                field_index = part.layer.fields().indexOf(field_name)
                if str(main_choice) in {
                    str(value) for value in part.layer.uniqueValues(field_index)
                }:
                    return part
        for part in self.parts:
            if part.name == main_choice:
                return part
        return self.parts[0]

    def _feature_selected(self, feature, layer, main_choice):
        if not self.layer_values:
            return True
        field_name = find_field(layer, LAYER_FIELD_CANDIDATES)
        return field_name and str(feature[field_name]) == str(main_choice)

    def _source_features(self, layer, main_choice):
        return [
            feature
            for feature in layer.getFeatures()
            if feature.hasGeometry() and self._feature_selected(feature, layer, main_choice)
        ]

    def _polygon_geometries(self, layer, main_choice):
        features = self._source_features(layer, main_choice)
        if not features:
            raise ConversionError(
                "The selected main boundary layer contains no geometry.")
        geometry_type = QgsWkbTypes.geometryType(layer.wkbType())
        if geometry_type == QgsWkbTypes.PolygonGeometry:
            return [(QgsGeometry(feature.geometry()), feature) for feature in features]
        if geometry_type != QgsWkbTypes.LineGeometry:
            raise ConversionError(
                "The main boundary must contain polygon or line geometry.")

        lines = [QgsGeometry(feature.geometry())
                 for feature in features if not feature.geometry().isEmpty()]
        self._message(
            "Polygonizing {} boundary features...".format(len(lines)))
        noded = QgsGeometry.unaryUnion(lines)
        noded_parts = noded.asGeometryCollection()
        polygonized = QgsGeometry.polygonize(noded_parts or [noded])
        if polygonized.isNull() or polygonized.isEmpty():
            raise ConversionError(
                "No polygon could be created. Repair gaps, open boundaries, overshoots, and duplicate lines."
            )
        parts = polygonized.asGeometryCollection()
        if not parts and QgsWkbTypes.geometryType(
                polygonized.wkbType()) == QgsWkbTypes.PolygonGeometry:
            parts = [polygonized]
        if not parts:
            raise ConversionError("Polygonize returned no polygon parts.")

        source_index = QgsSpatialIndex()
        for source_feature in features:
            source_index.addFeature(source_feature)
        feature_by_id = {feature.id(): feature for feature in features}
        output = []
        for geometry in parts:
            point = geometry.pointOnSurface().asPoint()
            nearest = source_index.nearestNeighbor(point, 1)
            source_feature = feature_by_id.get(
                nearest[0]) if nearest else features[0]
            output.append((geometry, source_feature))
        return output

    def _target_crs(self, source_crs, source_crs_override, target_crs):
        source = source_crs_override if source_crs_override and source_crs_override.isValid() else source_crs
        if not source or not source.isValid():
            raise ConversionError(
                "The source CRS is unknown. Select the correct source CRS.")
        target = target_crs if target_crs and target_crs.isValid() else source
        return source, target

    def _text_records(self, selected_layers):
        records = {name: [] for name in selected_layers}
        if not selected_layers:
            return records
        for part in self.parts:
            layer = part.layer
            layer_field = find_field(layer, LAYER_FIELD_CANDIDATES)
            text_field = find_field(layer, TEXT_FIELD_CANDIDATES)
            if not layer_field or not text_field:
                continue
            for feature in layer.getFeatures():
                layer_name = str(feature[layer_field])
                if layer_name not in records or not feature.hasGeometry():
                    continue
                value = feature[text_field]
                if value in (None, ""):
                    continue
                geometry = feature.geometry()
                if geometry.isEmpty():
                    continue
                if QgsWkbTypes.geometryType(
                        geometry.wkbType()) == QgsWkbTypes.PointGeometry:
                    point = geometry.asPoint() if not geometry.isMultipart(
                    ) else geometry.asMultiPoint()[0]
                    point_geometry = QgsGeometry.fromPointXY(point)
                else:
                    point_geometry = geometry.pointOnSurface()
                records[layer_name].append((point_geometry, str(value)))
        return records

    def _join_text_value(self, polygon, records):
        inside = []
        for point, value in records:
            try:
                matched = polygon.contains(point) or polygon.intersects(point)
            except (AttributeError, RuntimeError):
                matched = False
            if matched:
                inside.append(value)
        if inside:
            return " | ".join(dict.fromkeys(inside))
        if not records:
            return None
        centre = polygon.pointOnSurface()
        nearest = min(records, key=lambda item: centre.distance(item[0]))
        return nearest[1]

    def build_polygon_layer(
        self,
        main_choice,
        selected_values,
        source_crs_override=None,
        target_crs=None,
        shapefile_names=False,
    ):
        part = self._main_part(main_choice)
        source_layer = part.layer
        source_crs, output_crs = self._target_crs(
            source_layer.crs(), source_crs_override, target_crs
        )
        polygons = self._polygon_geometries(source_layer, main_choice)

        is_cad = self.source_format == "CAD"
        selected_values = list(selected_values or [])
        field_map = []
        used = set()
        if is_cad:
            for layer_name in selected_values:
                field_map.append(
                    (layer_name,
                     safe_name(
                         layer_name,
                         used,
                         shapefile_names,
                         force_sfc=True)))
        else:
            available = {
                field.name(): field for field in source_layer.fields()}
            for name in selected_values:
                if name not in available:
                    continue
                field_map.append(
                    (name, safe_name(name, used, shapefile_names)))

        output = QgsVectorLayer("Polygon", "SFC_Polygon", "memory")
        output.setCrs(output_crs)
        provider = output.dataProvider()
        fields = []
        for _source_name, output_name in field_map:
            fields.append(QgsField(output_name, QVariant.String, len=254))
        provider.addAttributes(fields)
        output.updateFields()

        transform = None
        if source_crs != output_crs:
            transform = QgsCoordinateTransform(
                source_crs,
                output_crs,
                QgsProject.instance().transformContext(),
            )
        text_records = self._text_records(selected_values) if is_cad else {}
        output_features = []
        for geometry, source_feature in polygons:
            source_geometry = QgsGeometry(geometry)
            attributes = []
            for source_name, _output_name in field_map:
                if is_cad:
                    attributes.append(
                        self._join_text_value(
                            source_geometry,
                            text_records.get(source_name, []),
                        )
                    )
                else:
                    try:
                        value = source_feature[source_name]
                    except Exception:
                        value = None
                    attributes.append(None if value is None else str(value))
            output_geometry = QgsGeometry(source_geometry)
            if transform is not None:
                try:
                    output_geometry.transform(transform)
                except Exception as error:
                    raise ConversionError(
                        "Coordinate transformation failed: {}".format(error))
            feature = QgsFeature(output.fields())
            feature.setGeometry(output_geometry)
            feature.setAttributes(attributes)
            output_features.append(feature)
        provider.addFeatures(output_features)
        output.updateExtents()
        if output.featureCount() < 1:
            raise ConversionError("The polygon output is empty.")
        return output

    def _write_layer(self, layer, path, driver):
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = driver
        options.fileEncoding = "UTF-8"
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer,
            path,
            QgsProject.instance().transformContext(),
            options,
        )
        error_code = result[0] if isinstance(result, tuple) else result
        if error_code != QgsVectorFileWriter.NoError:
            message = result[1] if isinstance(
                result, tuple) and len(result) > 1 else str(result)
            raise ConversionError("Output writer failed: {}".format(message))

    def _polygon_boundary(self, geometry):
        abstract_geometry = None if geometry.isNull() else geometry.constGet()
        boundary_abstract = abstract_geometry.boundary(
        ) if abstract_geometry is not None else None
        boundary = QgsGeometry(
            boundary_abstract) if boundary_abstract is not None else QgsGeometry()
        if not boundary.isNull() and not boundary.isEmpty():
            if not QgsWkbTypes.isMultiType(boundary.wkbType()):
                boundary.convertToMultiType()
        return boundary

    @staticmethod
    def _set_ogr_field(feature, name, value):
        if feature.GetFieldIndex(name) >= 0:
            feature.SetField(name, value)

    @staticmethod
    def _dxf_label_style(text, height):
        escaped = str(text).replace("\r", " ").replace("\n", " ")
        escaped = escaped.replace("\\", "\\\\").replace('"', '\\"')
        return 'LABEL(f:"Arial",s:{:.9g}g,t:"{}",c:#000000,p:5)'.format(
            height,
            escaped,
        )

    def _write_dxf(self, polygon_layer, path, source_layer_name):
        try:
            from osgeo import ogr
        except Exception as error:
            raise ConversionError(
                "GDAL/OGR DXF support is not available: {}".format(error))

        driver = ogr.GetDriverByName("DXF")
        if driver is None:
            raise ConversionError(
                "The GDAL DXF writer is not available in this QGIS installation.")
        if os.path.exists(path):
            try:
                driver.DeleteDataSource(path)
            except Exception:
                os.remove(path)
        dataset = driver.CreateDataSource(path)
        if dataset is None:
            raise ConversionError("DXF output could not be created.")
        entities = dataset.CreateLayer("entities", geom_type=ogr.wkbUnknown)
        if entities is None:
            dataset = None
            raise ConversionError(
                "The DXF entities layer could not be created.")

        attribute_fields = list(polygon_layer.fields())
        field_layers = [
            (field, safe_cad_layer(field.name(), "SFC_FIELD"))
            for field in attribute_fields
        ]
        if not field_layers:
            field_layers = [(None, safe_cad_layer(
                source_layer_name, "SFC_POLYGON"))]
        boundary_count = 0
        label_count = 0
        polygon_count = 0
        cad_layers = set()
        for source in polygon_layer.getFeatures():
            source_geometry = source.geometry()
            boundary = self._polygon_boundary(source_geometry)
            if boundary.isNull() or boundary.isEmpty():
                continue
            ogr_boundary = ogr.CreateGeometryFromWkb(bytes(boundary.asWkb()))
            if ogr_boundary is None:
                continue
            polygon_count += 1

            for _field, layer_name in field_layers:
                line_feature = ogr.Feature(entities.GetLayerDefn())
                self._set_ogr_field(line_feature, "Layer", layer_name)
                line_feature.SetGeometry(ogr_boundary)
                line_feature.SetStyleString("PEN(c:#000000)")
                if entities.CreateFeature(line_feature) != 0:
                    dataset = None
                    raise ConversionError(
                        "A polygon boundary could not be written to DXF.")
                line_feature = None
                boundary_count += 1
                cad_layers.add(layer_name)

            labels = []
            for field, layer_name in field_layers:
                if field is None:
                    continue
                value = source[field.name()]
                if value in (None, ""):
                    continue
                labels.append((layer_name, str(value)))
            if not labels:
                continue

            box = source_geometry.boundingBox()
            width = abs(box.width())
            height = abs(box.height())
            short_side = min(width, height)
            if short_side <= 0:
                continue
            longest_text = max(len(text) for _layer_name, text in labels)
            text_height = min(
                short_side * 0.04,
                (width * 0.75) / max(8.0, longest_text * 0.62),
            )
            stack_limit = short_side * 0.68 / max(1.0, 1.55 * len(labels))
            text_height = max(short_side * 0.008,
                              min(text_height, stack_limit))
            spacing = text_height * 1.55
            anchor = source_geometry.pointOnSurface()
            if anchor.isNull() or anchor.isEmpty():
                continue
            point = anchor.asPoint()
            first_y = point.y() + (spacing * (len(labels) - 1) / 2.0)

            for row, (layer_name, text) in enumerate(labels):
                ogr_point = ogr.Geometry(ogr.wkbPoint)
                ogr_point.AddPoint(
                    float(point.x()), float(first_y - row * spacing))
                text_feature = ogr.Feature(entities.GetLayerDefn())
                self._set_ogr_field(text_feature, "Layer", layer_name)
                self._set_ogr_field(text_feature, "Text", text)
                text_feature.SetGeometry(ogr_point)
                text_feature.SetStyleString(
                    self._dxf_label_style(text, text_height))
                if entities.CreateFeature(text_feature) != 0:
                    dataset = None
                    raise ConversionError(
                        "An attribute label could not be written to DXF.")
                text_feature = None
                label_count += 1

        dataset.FlushCache()
        dataset = None
        if boundary_count < 1:
            raise ConversionError(
                "No closed polygon boundary was available for DXF export.")
        self._message(
            "DXF entities written: {} polygons, {} field layers, {} boundary entities, "
            "and {} attribute labels.".format(
                polygon_count,
                len(cad_layers),
                boundary_count,
                label_count,
            )
        )

    def convert(
        self,
        main_choice,
        selected_values,
        output_format,
        output_folder,
        output_name,
        source_crs_override=None,
        target_crs=None,
        add_to_project=True,
    ):
        if not self.parts:
            raise ConversionError(
                "Inspect the source before running conversion.")
        if not os.path.isdir(output_folder):
            raise ConversionError("Output folder does not exist.")
        output_name = safe_name(output_name or "SFC_Output")
        output_format = str(output_format).upper()
        if output_format in ("KML", "KMZ"):
            target_crs = QgsCoordinateReferenceSystem("EPSG:4326")
            self._message("KML/KMZ output CRS set to WGS 84 (EPSG:4326).")
        polygon_layer = self.build_polygon_layer(
            main_choice,
            selected_values,
            source_crs_override,
            target_crs,
            shapefile_names=(output_format == "SHP"),
        )

        if output_format == "SHP":
            output_path = os.path.join(output_folder, output_name + ".shp")
            self._write_layer(polygon_layer, output_path, "ESRI Shapefile")
        elif output_format == "KML":
            output_path = os.path.join(output_folder, output_name + ".kml")
            self._write_layer(polygon_layer, output_path, "KML")
        elif output_format == "KMZ":
            output_path = os.path.join(output_folder, output_name + ".kmz")
            with tempfile.TemporaryDirectory(prefix="sfc_kmz_") as folder:
                kml_path = os.path.join(folder, "doc.kml")
                self._write_layer(polygon_layer, kml_path, "KML")
                with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.write(kml_path, "doc.kml")
        elif output_format == "DXF":
            output_path = os.path.join(output_folder, output_name + ".dxf")
            self._write_dxf(polygon_layer, output_path, main_choice)
        else:
            raise ConversionError(
                "Unsupported output format: {}".format(output_format))

        if not os.path.isfile(output_path):
            raise ConversionError("The output file was not created.")
        if add_to_project and output_format in ("SHP", "KML"):
            layer = QgsVectorLayer(output_path, output_name, "ogr")
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
        self._message("Output created: {}".format(output_path))
        return output_path
