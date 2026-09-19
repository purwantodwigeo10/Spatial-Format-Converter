# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import re

from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices, QIcon, QPixmap
from qgis.PyQt.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)
from qgis.gui import QgsProjectionSelectionWidget

from .converter import ConversionEngine, ConversionError
from .license_manager import (
    LicenseError,
    USER_GUIDE_URL,
    access_status,
    activate,
    device_id,
    record_success,
    refresh,
    request_page_url,
    require_access,
)


def _plugin_icon():
    return QIcon(os.path.join(os.path.dirname(__file__), "icon.png"))


STATUS_COLOURS = {
    "active": "#188038",
    "trial": "#e67e22",
    "inactive": "#c62828",
}

STATUS_BACKGROUNDS = {
    "active": "#eaf9f3",
    "trial": "#fff4e5",
    "inactive": "#fff0f2",
}

STATUS_BORDERS = {
    "active": "#9ad8c2",
    "trial": "#f0c27b",
    "inactive": "#efabb6",
}

APP_STYLE = """
QDialog {
    background: #f6f8fc;
    color: #17213c;
    font-family: "Segoe UI";
    font-size: 9pt;
}
QGroupBox {
    background: #ffffff;
    border: 1px solid #dfe4f1;
    border-radius: 12px;
    margin-top: 14px;
    padding: 15px 10px 10px 10px;
    font-weight: 700;
    color: #17213c;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 7px;
    color: #2516b8;
    background: #ffffff;
}
QGroupBox#sfcHeader {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #ffffff, stop:0.52 #f0f2ff, stop:1 #e9fbfc);
    border: 1px solid #d7ddef;
    border-radius: 18px;
    margin-top: 0;
    padding: 10px;
}
QFrame#heroHeader {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #ffffff, stop:0.52 #f0f2ff, stop:1 #e9fbfc);
    border: 1px solid #d7ddef;
    border-radius: 18px;
}
QFrame#card {
    background: #ffffff;
    border: 1px solid #dfe4f1;
    border-radius: 14px;
}
QLabel#cardTitle {
    color: #2516b8;
    font-size: 11pt;
    font-weight: 700;
    border: 0;
    background: transparent;
    padding: 0;
}
QLabel#cardHint {
    color: #65708a;
    font-size: 9pt;
    border: 0;
    background: transparent;
}
QLabel#activationHeading {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #2516b8, stop:0.55 #4b50df, stop:1 #47d4dc);
    color: white;
    border-radius: 14px;
    padding: 16px 20px;
}
QLineEdit, QComboBox, QListWidget, QPlainTextEdit {
    background: #ffffff;
    color: #17213c;
    border: 1px solid #cfd6e8;
    border-radius: 8px;
    padding: 6px 8px;
    selection-background-color: #4b50df;
    selection-color: #ffffff;
}
QLineEdit:focus, QComboBox:focus, QListWidget:focus, QPlainTextEdit:focus {
    border: 2px solid #4b50df;
}
QLineEdit:read-only {
    background: #f0f2f8;
    color: #5d6884;
}
QComboBox::drop-down {
    border: 0;
    width: 28px;
}
QListWidget::item {
    min-height: 26px;
    border-radius: 6px;
    padding: 3px;
}
QListWidget::item:hover {
    background: #eef0ff;
}
QListWidget::item:selected {
    background: #4b50df;
    color: white;
}
QPushButton {
    min-height: 27px;
    padding: 3px 11px;
    border: 1px solid #cfd6e8;
    border-radius: 8px;
    background: #ffffff;
    color: #2516b8;
    font-weight: 600;
}
QPushButton:hover {
    background: #f0f2ff;
    border-color: #4b50df;
}
QPushButton:pressed {
    background: #e2e5ff;
}
QPushButton:disabled {
    background: #eef0f5;
    color: #9aa3b9;
    border-color: #dfe4ec;
}
QPushButton#primaryButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #2516b8, stop:0.62 #4b50df, stop:1 #407fdc);
    color: #ffffff;
    border: 0;
    font-weight: 700;
    min-height: 29px;
}
QPushButton#primaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #3725ca, stop:0.62 #5d64ed, stop:1 #47a5df);
}
QPushButton#guideButton {
    background: #e9fbfc;
    color: #185d79;
    border: 1px solid #92e2e6;
}
QPushButton#guideButton:hover {
    background: #d7f7f9;
    border-color: #47d4dc;
}
QCheckBox {
    spacing: 8px;
    color: #3f4965;
}
QPlainTextEdit {
    background: #111831;
    color: #dce2f4;
    border: 1px solid #252f51;
    font-family: "Cascadia Mono", "Consolas";
}
QToolTip {
    background: #17213c;
    color: white;
    border: 1px solid #4b50df;
    padding: 5px;
}
"""


def _activation_status_data(check_online=False):
    mode, message, _state = access_status(check_online=check_online)
    if mode not in STATUS_COLOURS:
        mode = "inactive"
    return mode, message


def _apply_activation_badge(
        label_widget,
        check_online=False,
        prefix=True,
        compact=False):
    mode, message = _activation_status_data(check_online)
    colour = STATUS_COLOURS.get(mode, STATUS_COLOURS["inactive"])
    background = STATUS_BACKGROUNDS[mode]
    border = STATUS_BORDERS[mode]
    status = mode.upper()
    text = status
    if compact and mode == "trial":
        remaining = ""
        match = re.search(r"(\d+)", message or "")
        if match:
            remaining = " | Remaining: %s" % match.group(1)
        text = "TRIAL" + remaining
    elif compact and mode == "inactive":
        text = "INACTIVE"
    elif mode in ("trial", "inactive") and message:
        text += " — " + message
    if prefix:
        text = "Activation: " + text
    label_widget.setText(text)
    label_widget.setToolTip(message or status)
    padding = "3px 7px" if compact else "6px 10px"
    font_size = "8pt" if compact else "9pt"
    label_widget.setStyleSheet(
        "QLabel {"
        " color: %s;"
        " background: %s;"
        " border: 1px solid %s;"
        " border-radius: 8px;"
        " padding: %s;"
        " font-size: %s;"
        " font-weight: 700;"
        "}" % (colour, background, border, padding, font_size)
    )


def _enable_window_controls(dialog):
    dialog.setWindowFlags(
        Qt.Window
        | Qt.WindowTitleHint
        | Qt.WindowSystemMenuHint
        | Qt.WindowMinimizeButtonHint
        | Qt.WindowMaximizeButtonHint
        | Qt.WindowCloseButtonHint
    )


class ActivationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Spatial Format Converter — Activation")
        self.setWindowIcon(_plugin_icon())
        _enable_window_controls(self)
        self.setStyleSheet(APP_STYLE)
        self.setMinimumWidth(580)
        self.resize(680, 400)
        self._build_ui()
        self.refresh_status(False)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        heading = QLabel(
            "<div style='font-size:22px; font-weight:700;'>Spatial Format Converter</div>"
            "<div style='margin-top:4px;'>Secure license activation and synchronization for QGIS</div>")
        heading.setObjectName("activationHeading")
        layout.addWidget(heading)

        form_group = QGroupBox("Activation and Device")
        form = QFormLayout(form_group)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        form.addRow("Activation Status", self.status_label)

        device_row = QWidget()
        device_layout = QHBoxLayout(device_row)
        device_layout.setContentsMargins(0, 0, 0, 0)
        self.device_edit = QLineEdit(device_id())
        self.device_edit.setReadOnly(True)
        copy_button = QPushButton("Copy")
        copy_button.clicked.connect(self.copy_device)
        device_layout.addWidget(self.device_edit, 1)
        device_layout.addWidget(copy_button)
        form.addRow("Device ID", device_row)

        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText(
            "Paste the activation data received from License Hub")
        form.addRow("Activation Code", self.code_edit)
        layout.addWidget(form_group)

        actions = QHBoxLayout()
        request_button = QPushButton("Open Activation Page")
        request_button.setObjectName("guideButton")
        request_button.clicked.connect(self.open_request)
        guide_button = QPushButton("User Guide")
        guide_button.setObjectName("guideButton")
        guide_button.clicked.connect(self.open_guide)
        sync_button = QPushButton("Synchronize")
        sync_button.clicked.connect(self.synchronize)
        activate_button = QPushButton("Activate")
        activate_button.setObjectName("primaryButton")
        activate_button.setDefault(True)
        activate_button.clicked.connect(self.apply_activation)
        actions.addWidget(request_button)
        actions.addWidget(guide_button)
        actions.addStretch(1)
        actions.addWidget(sync_button)
        actions.addWidget(activate_button)
        layout.addLayout(actions)

        close_buttons = QDialogButtonBox(QDialogButtonBox.Close)
        close_buttons.rejected.connect(self.close)
        layout.addWidget(close_buttons)

    def copy_device(self):
        QApplication.clipboard().setText(self.device_edit.text())

    def open_request(self):
        QDesktopServices.openUrl(QUrl(request_page_url()))

    def open_guide(self):
        QDesktopServices.openUrl(QUrl(USER_GUIDE_URL))

    def refresh_status(self, online=False):
        try:
            _apply_activation_badge(self.status_label, online, prefix=False)
        except Exception as error:
            self.status_label.setText("INACTIVE — {}".format(error))
            self.status_label.setStyleSheet(
                "QLabel { color:#c62828; background:#fff0f2; border:1px solid #efabb6;"
                " border-radius:9px; padding:6px 10px; font-weight:700; }"
            )

    def synchronize(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            result, message, _state = refresh()
        finally:
            QApplication.restoreOverrideCursor()
        self.refresh_status(False)
        if result is True:
            QMessageBox.information(self, "Spatial Format Converter", message)
        elif result is False:
            QMessageBox.warning(self, "Spatial Format Converter", message)
        else:
            QMessageBox.warning(self, "Spatial Format Converter", message)

    def apply_activation(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            success, message = activate(self.code_edit.text())
        finally:
            QApplication.restoreOverrideCursor()
        self.refresh_status(False)
        if success:
            self.code_edit.clear()
            QMessageBox.information(self, "Spatial Format Converter", message)
        else:
            QMessageBox.critical(self, "Activation failed", message)


class ConverterDialog(QDialog):
    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.engine = ConversionEngine(self._log)
        self.inspection = None
        self.setWindowTitle("Spatial Format Converter — QGIS")
        self.setWindowIcon(_plugin_icon())
        _enable_window_controls(self)
        self.setStyleSheet(APP_STYLE)
        self.setMinimumSize(820, 560)
        self.resize(1000, 660)
        self._build_ui()

    def _path_row(self, line_edit, callback, button_text="Browse…"):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        button = QPushButton(button_text)
        button.clicked.connect(callback)
        layout.addWidget(line_edit, 1)
        layout.addWidget(button)
        return widget

    def _card(self, title, hint=""):
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 11, 14, 11)
        layout.setSpacing(7)
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        layout.addWidget(title_label)
        if hint:
            hint_label = QLabel(hint)
            hint_label.setObjectName("cardHint")
            hint_label.setWordWrap(True)
            layout.addWidget(hint_label)
        return card, layout

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)
        root.addWidget(self._build_header())

        content = QHBoxLayout()
        content.setSpacing(10)
        left_column = QVBoxLayout()
        left_column.setSpacing(10)
        right_column = QVBoxLayout()
        right_column.setSpacing(10)

        source_card, source_layout = self._card(
            "Source Dataset",
            "Select a spatial source. Format, layers, and transferable attributes are detected automatically.",
        )
        source_form = QFormLayout()
        source_form.setHorizontalSpacing(12)
        source_form.setVerticalSpacing(9)
        self.input_edit = QLineEdit()
        self.input_edit.editingFinished.connect(self.inspect_source)
        source_form.addRow("Input File", self._path_row(
            self.input_edit, self.browse_input))
        self.format_edit = QLineEdit()
        self.format_edit.setReadOnly(True)
        source_form.addRow("Detected Format", self.format_edit)
        self.main_combo = QComboBox()
        source_form.addRow("Main Boundary Layer", self.main_combo)
        source_layout.addLayout(source_form)
        left_column.addWidget(source_card)

        attributes_card, attributes_layout = self._card(
            "Attributes and CAD Text Layers",
            "Choose only semantic information that must be carried to the output.",
        )
        self.attribute_list = QListWidget()
        self.attribute_list.setMinimumHeight(145)
        attributes_layout.addWidget(self.attribute_list, 1)
        selection_buttons = QHBoxLayout()
        select_all = QPushButton("Select All")
        select_all.clicked.connect(lambda: self.set_all_checks(Qt.Checked))
        unselect_all = QPushButton("Unselect All")
        unselect_all.clicked.connect(lambda: self.set_all_checks(Qt.Unchecked))
        selection_buttons.addWidget(select_all)
        selection_buttons.addWidget(unselect_all)
        selection_buttons.addStretch(1)
        attributes_layout.addLayout(selection_buttons)
        left_column.addWidget(attributes_card, 1)

        crs_card, crs_layout = self._card(
            "Coordinate Reference System",
            "Define the source CRS correctly before applying an output transformation.",
        )
        self.transform_check = QCheckBox("Transform coordinates for output")
        self.transform_check.toggled.connect(self._update_crs_enabled)
        self.source_crs = QgsProjectionSelectionWidget()
        self.target_crs = QgsProjectionSelectionWidget()
        crs_form = QFormLayout()
        crs_form.setVerticalSpacing(9)
        crs_form.addRow("Source CRS", self.source_crs)
        crs_form.addRow("Target CRS", self.target_crs)
        crs_layout.addWidget(self.transform_check)
        crs_layout.addLayout(crs_form)
        right_column.addWidget(crs_card)

        output_card, output_layout = self._card(
            "Output Configuration",
            "Polygon output is validated before it is written to the selected format.",
        )
        output_form = QFormLayout()
        output_form.setHorizontalSpacing(12)
        output_form.setVerticalSpacing(9)
        self.output_format = QComboBox()
        self.output_format.addItems(["SHP", "KML", "KMZ", "DXF"])
        output_form.addRow("Output Format", self.output_format)
        self.output_folder = QLineEdit()
        output_form.addRow("Output Folder", self._path_row(
            self.output_folder, self.browse_output))
        self.output_name = QLineEdit("SFC_Output")
        output_form.addRow("Output Name", self.output_name)
        self.add_project = QCheckBox(
            "Add compatible output to the current QGIS project")
        self.add_project.setChecked(True)
        output_layout.addLayout(output_form)
        output_layout.addWidget(self.add_project)
        right_column.addWidget(output_card, 1)

        content.addLayout(left_column, 3)
        content.addLayout(right_column, 2)
        root.addLayout(content, 1)

        log_card, log_layout = self._card("Activity Log")
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumBlockCount(500)
        self.log_edit.setFixedHeight(72)
        self.log_edit.setPlaceholderText(
            "Conversion messages will appear here.")
        log_layout.addWidget(self.log_edit)
        root.addWidget(log_card)

        footer = QHBoxLayout()
        footer.addStretch(1)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        self.run_button = QPushButton("Convert Polygon Data")
        self.run_button.setObjectName("primaryButton")
        self.run_button.setMinimumWidth(160)
        self.run_button.setDefault(True)
        self.run_button.clicked.connect(self.run_conversion)
        footer.addWidget(close_button)
        footer.addWidget(self.run_button)
        root.addLayout(footer)

        self._update_crs_enabled(False)

    def _build_header(self):
        header = QFrame()
        header.setObjectName("heroHeader")
        header.setMinimumHeight(118)
        layout = QGridLayout(header)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setHorizontalSpacing(14)

        logo_label = QLabel()
        logo_label.setFixedSize(132, 88)
        logo_label.setAlignment(Qt.AlignCenter)
        original = QPixmap(os.path.join(os.path.dirname(__file__), "icon.png"))
        if not original.isNull():
            crop_x = int(original.width() * 0.47)
            symbol = original.copy(crop_x, 0, original.width() -
                                   crop_x, original.height())
            logo_label.setPixmap(
                symbol.scaled(
                    logo_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
        else:
            logo_label.setText("SFC")
            logo_label.setStyleSheet(
                "font-size:32px; font-weight:800; color:#2516b8;")
        layout.addWidget(logo_label, 0, 0, 3, 1)

        edition = QLabel("QGIS EDITION")
        edition.setStyleSheet(
            "QLabel { color:#274d7a; background:#dff9fa; border:1px solid #8de0e4;"
            " border-radius:8px; padding:3px 8px; font-size:8pt; font-weight:700; }"
        )
        edition.setMaximumWidth(108)
        title = QLabel("Spatial Format Converter")
        title.setStyleSheet(
            "QLabel { color:#17213c; font-size:20px; font-weight:750; background:transparent; border:0; }"
        )
        description = QLabel(
            "Structured polygon interoperability for SHP, KML/KMZ, and CAD — "
            "with CRS transformation and controlled semantic attribute mapping."
        )
        description.setStyleSheet(
            "QLabel { color:#5d6884; font-size:10pt; background:transparent; border:0; }"
        )
        description.setWordWrap(True)
        description.setMaximumWidth(390)
        layout.addWidget(edition, 0, 1, Qt.AlignLeft)
        layout.addWidget(title, 1, 1)
        layout.addWidget(description, 2, 1)
        layout.setColumnStretch(1, 1)

        status_widget = QWidget()
        status_widget.setFixedWidth(285)
        status_layout = QVBoxLayout(status_widget)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(4)
        plugin_status = QLabel("Plugin: Ready  |  Service: Enabled")
        plugin_status.setAlignment(Qt.AlignCenter)
        plugin_status.setFixedHeight(25)
        plugin_status.setStyleSheet(
            "QLabel { color:#188038; background:#eaf9f3; border:1px solid #9ad8c2;"
            " border-radius:8px; padding:3px 7px; font-size:8pt; font-weight:700; }"
        )
        self.license_label = QLabel()
        self.license_label.setAlignment(Qt.AlignCenter)
        self.license_label.setFixedHeight(25)
        self.license_label.setWordWrap(False)
        self._refresh_license_label()
        action_row = QHBoxLayout()
        action_row.setSpacing(6)
        activation_button = QPushButton("Manage Activation")
        activation_button.setObjectName("primaryButton")
        activation_button.setFixedHeight(26)
        activation_button.clicked.connect(self.open_activation)
        guide_button = QPushButton("User Guide")
        guide_button.setObjectName("guideButton")
        guide_button.setFixedHeight(26)
        guide_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(USER_GUIDE_URL))
        )
        action_row.addWidget(activation_button)
        action_row.addWidget(guide_button)
        status_layout.addWidget(plugin_status)
        status_layout.addWidget(self.license_label)
        status_layout.addLayout(action_row)
        status_layout.addStretch(1)
        layout.addWidget(status_widget, 0, 2, 3, 1)
        return header

    def _refresh_license_label(self):
        _apply_activation_badge(self.license_label, False,
                                prefix=True, compact=True)

    def showEvent(self, event):
        self._refresh_license_label()
        super().showEvent(event)

    def open_activation(self):
        dialog = ActivationDialog(self)
        dialog.exec_()
        self._refresh_license_label()

    def browse_input(self):
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Select Spatial Dataset",
            self.input_edit.text() or "",
            "Spatial Data (*.shp *.kml *.kmz *.dwg *.dxf *.dgn);;All Files (*.*)",
        )
        if path:
            self.input_edit.setText(path)
            self.inspect_source()

    def browse_output(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder",
            self.output_folder.text() or "",
        )
        if folder:
            self.output_folder.setText(folder)

    def inspect_source(self):
        path = self.input_edit.text().strip()
        if not path:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.inspection = self.engine.inspect(path)
            self.format_edit.setText(self.inspection["format"])
            self.main_combo.clear()
            self.main_combo.addItems(self.inspection["main_choices"])
            self.attribute_list.blockSignals(True)
            self.attribute_list.clear()
            for value in self.inspection["attribute_choices"]:
                item = QListWidgetItem(value)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                self.attribute_list.addItem(item)
            self.attribute_list.blockSignals(False)
            source_crs = self.inspection.get("source_crs")
            if source_crs and source_crs.isValid():
                self.source_crs.setCrs(source_crs)
                self.target_crs.setCrs(source_crs)
            if not self.output_folder.text():
                self.output_folder.setText(os.path.dirname(path))
            self.output_name.setText(os.path.splitext(
                os.path.basename(path))[0] + "_SFC")
            self._log(
                "Detected {}: {} main-layer choices, {} transferable choices.".format(
                    self.inspection["format"],
                    len(self.inspection["main_choices"]),
                    len(self.inspection["attribute_choices"]),
                )
            )
        except Exception as error:
            self.inspection = None
            QMessageBox.critical(self, "Source inspection failed", str(error))
        finally:
            QApplication.restoreOverrideCursor()

    def selected_values(self):
        return [
            self.attribute_list.item(index).text()
            for index in range(self.attribute_list.count())
            if self.attribute_list.item(index).checkState() == Qt.Checked
        ]

    def set_all_checks(self, state):
        self.attribute_list.blockSignals(True)
        try:
            for index in range(self.attribute_list.count()):
                self.attribute_list.item(index).setCheckState(state)
        finally:
            self.attribute_list.blockSignals(False)

    def _update_crs_enabled(self, enabled):
        self.target_crs.setEnabled(bool(enabled))

    def _log(self, message):
        self.log_edit.appendPlainText(str(message))
        QApplication.processEvents()

    def run_conversion(self):
        if self.inspection is None:
            self.inspect_source()
        if self.inspection is None:
            return
        self.run_button.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            access_mode, access_message = require_access()
            self._log("License: {}".format(access_message))
            target_crs = self.target_crs.crs() if self.transform_check.isChecked() else None
            source_override = self.source_crs.crs()
            output_path = self.engine.convert(
                main_choice=self.main_combo.currentText(),
                selected_values=self.selected_values(),
                output_format=self.output_format.currentText(),
                output_folder=self.output_folder.text().strip(),
                output_name=self.output_name.text().strip(),
                source_crs_override=source_override,
                target_crs=target_crs,
                add_to_project=self.add_project.isChecked(),
            )
            record_success(access_mode)
            self._refresh_license_label()
            QMessageBox.information(
                self,
                "Conversion completed",
                "Output created successfully:\n{}".format(output_path),
            )
        except (ConversionError, LicenseError) as error:
            self._log("ERROR: {}".format(error))
            QMessageBox.critical(self, "Spatial Format Converter", str(error))
        except Exception as error:
            self._log("UNEXPECTED ERROR: {}".format(error))
            QMessageBox.critical(
                self,
                "Unexpected error",
                "{}\n\nOpen View → Panels → Log Messages for additional QGIS diagnostics.".format(
                    error),
            )
        finally:
            QApplication.restoreOverrideCursor()
            self.run_button.setEnabled(True)
