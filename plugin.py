# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later

from qgis.PyQt.QtCore import QCoreApplication, QUrl
from qgis.PyQt.QtGui import QDesktopServices, QIcon
from qgis.PyQt.QtWidgets import QAction

from .dialogs import ActivationDialog, ConverterDialog
from .license_manager import USER_GUIDE_URL


class SpatialFormatConverterPlugin:
    """QGIS plugin entry point."""

    def __init__(self, iface):
        self.iface = iface
        self.menu_name = self.tr("&Spatial Format Converter")
        self.toolbar = None
        self.actions = []
        self.converter_dialog = None
        self.activation_dialog = None

    def tr(self, text):
        return QCoreApplication.translate("SpatialFormatConverter", text)

    def _icon(self):
        import os
        return QIcon(os.path.join(os.path.dirname(__file__), "icon.png"))

    def _add_action(self, text, callback, icon=None, toolbar=False):
        action = QAction(icon or QIcon(), text, self.iface.mainWindow())
        action.setObjectName(
            "SpatialFormatConverter%sAction" % (len(self.actions) + 1)
        )
        action.triggered.connect(callback)
        self.iface.addPluginToVectorMenu(self.menu_name, action)
        if toolbar and self.toolbar is not None:
            self.toolbar.addAction(action)
        self.actions.append(action)
        return action

    def initGui(self):
        self.toolbar = self.iface.addToolBar("SpatialFormatConverterQGIS")
        self.toolbar.setObjectName("SpatialFormatConverterQGISToolbar")

        self._add_action(
            self.tr("Spatial Format Converter"),
            self.open_converter,
            self._icon(),
            toolbar=True,
        )
        self._add_action(self.tr("Manage Activation"), self.open_activation)
        self._add_action(self.tr("User Guide"), self.open_user_guide)

    def unload(self):
        for action in self.actions:
            try:
                self.iface.removePluginVectorMenu(self.menu_name, action)
            except (AttributeError, RuntimeError):
                action.deleteLater()
        if self.toolbar is not None:
            self.iface.mainWindow().removeToolBar(self.toolbar)
            self.toolbar.deleteLater()
        self.actions = []

    def open_converter(self):
        if self.converter_dialog is None:
            self.converter_dialog = ConverterDialog(self.iface)
        self.converter_dialog.show()
        self.converter_dialog.raise_()
        self.converter_dialog.activateWindow()

    def open_activation(self):
        if self.activation_dialog is None:
            self.activation_dialog = ActivationDialog(self.iface.mainWindow())
        self.activation_dialog.refresh_status(False)
        self.activation_dialog.show()
        self.activation_dialog.raise_()
        self.activation_dialog.activateWindow()

    def open_user_guide(self):
        QDesktopServices.openUrl(QUrl(USER_GUIDE_URL))
