# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later


def classFactory(iface):
    from .plugin import SpatialFormatConverterPlugin
    return SpatialFormatConverterPlugin(iface)
