# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit denial anywhere in the response takes precedence over success."""
def has_denial(value):
    if isinstance(value, list):
        return any(has_denial(item) for item in value)
    if not isinstance(value, dict):
        return False
    denied = {'inactive', 'expired', 'revoked', 'blocked', 'invalid', 'rejected',
              'disabled', 'deleted', 'deactivated', 'not_found', 'pending',
              'waiting', 'nonactive', 'nonaktif', 'tidak_aktif', 'kadaluarsa', 'kedaluwarsa'}
    for key, flag in value.items():
        normalized = str(flag).strip().lower().replace(' ', '_').replace('-', '_')
        if key in ('status', 'license_status', 'activation_status', 'state', 'approval_status', 'request_status') and normalized in denied:
            return True
        if key in ('active', 'valid', 'is_active', 'activated', 'approved') and normalized in ('false', '0', 'no'):
            return True
        if key in ('revoked', 'blocked', 'disabled', 'deleted', 'expired') and normalized in ('true', '1', 'yes'):
            return True
        if key in ('message', 'detail', 'msg', 'pesan'):
            message = str(flag).lower()
            if any(phrase in message for phrase in ('not active', 'not valid', 'inactive', 'revoked', 'blocked', 'expired', 'tidak aktif', 'tidak berhasil', 'aktivasi gagal', 'activation failed', 'license deleted')):
                return True
        if isinstance(flag, (dict, list)) and has_denial(flag):
            return True
    return False
