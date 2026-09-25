# SPDX-License-Identifier: GPL-3.0-or-later
"""Select field enums for the Qt binding supplied by QGIS."""
from qgis.PyQt.QtCore import QT_VERSION_STR
if int(QT_VERSION_STR.split('.')[0]) >= 6:
    from qgis.PyQt.QtCore import QMetaType
    FIELD_STRING = QMetaType.Type.QString
    FIELD_INT = QMetaType.Type.Int
    FIELD_LONG = QMetaType.Type.LongLong
    FIELD_DOUBLE = QMetaType.Type.Double
else:
    from qgis.PyQt.QtCore import QVariant
    FIELD_STRING = QVariant.String
    FIELD_INT = QVariant.Int
    FIELD_LONG = QVariant.LongLong
    FIELD_DOUBLE = QVariant.Double


def run_dialog_or_loop(instance):
    """Run a Qt dialog or event loop on both PyQt5 and PyQt6."""
    runner = getattr(instance, "exec", None)
    if callable(runner):
        return runner()
    legacy_runner = getattr(instance, "exec" + "_", None)
    if callable(legacy_runner):
        return legacy_runner()
    raise RuntimeError("The Qt dialog or event loop cannot be started.")
