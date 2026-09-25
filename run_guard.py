# SPDX-License-Identifier: GPL-3.0-or-later
from functools import wraps

def single_run(function):
    """Prevent nested event loops from starting the same operation twice."""
    @wraps(function)
    def wrapped(self, *args, **kwargs):
        if getattr(self, '_operation_running', False):
            return
        self._operation_running = True
        try:
            # Qt button signals may append a checked-state argument. The
            # guarded dialog actions do not accept signal payloads.
            return function(self)
        finally:
            self._operation_running = False
    return wrapped
