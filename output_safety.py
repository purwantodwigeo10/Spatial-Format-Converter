# SPDX-License-Identifier: GPL-3.0-or-later
"""Refuse existing destinations, including Shapefile companion files."""
from pathlib import Path

def ensure_new_output(path):
    target = Path(path).expanduser().absolute()
    if not target.parent.is_dir():
        raise RuntimeError("Output folder does not exist: %s" % target.parent)
    if target.suffix.lower() == '.shp':
        suffixes = {'.shp', '.shx', '.dbf', '.prj', '.cpg', '.qpj', '.qix', '.sbn', '.sbx', '.fix', '.shp.xml'}
        names = {target.stem.casefold() + suffix for suffix in suffixes}
    else:
        names = {target.name.casefold()}
    if any(p.name.casefold() in names for p in target.parent.iterdir()):
        raise RuntimeError("Output already exists. Choose a new filename to preserve existing data: %s" % target)
