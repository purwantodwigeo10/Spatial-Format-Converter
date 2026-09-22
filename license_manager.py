from .license_response import has_denial
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""License state and HTTPS activation for Spatial Format Converter."""

import datetime
import hashlib
import json
import os
import platform
import re
import socket
import sys
import uuid
from urllib.parse import urlencode

from .license_network import request_json

try:
    import winreg
except ImportError:
    winreg = None


PRODUCT_NAME = "Spatial Format Converter"
PRODUCT_CODE = "SLFTCR"
FIXED_CODE = "PAL"
PRODUCT_VERSION = "26.1.0"
APPLICATION_TYPE = "QGIS"
TRIAL_LIMIT = 2

LICENSE_HUB_BASE = "https://aktivasi.ruangspasial.my.id"
REQUEST_URL = LICENSE_HUB_BASE + "/request"
USER_GUIDE_URL = LICENSE_HUB_BASE + "/help/spatial-format-converter-qgis"
ACTIVATION_ENDPOINTS = (
    LICENSE_HUB_BASE + "/api/license/validate",
)
STATUS_ENDPOINTS = (
    LICENSE_HUB_BASE + "/api/license/status",
)
STATE_SIGNATURE_KEY = "RUANGSPASIAL-LICENSE-SPATIAL-FORMAT-CONVERTER-SLFTCR-PAL-V1"


class LicenseError(RuntimeError):
    pass


def _text(value):
    return "" if value is None else str(value)


def _utc_now():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _machine_guid():
    if winreg is None:
        return ""
    try:
        access = getattr(winreg, "KEY_READ", 0)
        access |= getattr(winreg, "KEY_WOW64_64KEY", 0)
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            access,
        )
        value, _kind = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        return _text(value).strip()
    except Exception:
        return ""


def device_name():
    return socket.gethostname() or platform.node() or "QGIS-DEVICE"


def device_id():
    # Keep the device identity algorithm identical to the ArcMap SFC build and
    # the other Ruang Spasial desktop tools.
    raw = "|".join(
        str(value or "").strip().upper()
        for value in (
            platform.system(),
            platform.release(),
            platform.machine(),
            device_name(),
            str(uuid.getnode()),
            _machine_guid(),
        )
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()[:32]


def _license_dir():
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser(
            "~/.local/share"
        )
    return os.path.join(
        base,
        "RuangSpasial",
        "LicenseHub",
        "SPATIAL_FORMAT_CONVERTER_QGIS_SLFTCR_PAL",
    )


def _license_file():
    return os.path.join(_license_dir(), "license.json")


def _default_state():
    return {
        "product": PRODUCT_NAME,
        "plugin_code": PRODUCT_CODE,
        "fixed_code": FIXED_CODE,
        "application": APPLICATION_TYPE,
        "version": PRODUCT_VERSION,
        "device_id": device_id(),
        "device_name": device_name(),
        "status": "trial",
        "trial_used": 0,
        "activation_code": "",
        "token": str(),
        "expires_at": "",
        "ever_activated": False,
        "last_check": "",
        "last_endpoint": "",
        "server_message": "",
    }


def _signature_payload(state):
    return {
        "product": state.get("product", ""),
        "plugin_code": state.get("plugin_code", ""),
        "fixed_code": state.get("fixed_code", ""),
        "application": state.get("application", ""),
        "device_id": state.get("device_id", ""),
        "status": state.get("status", ""),
        "trial_used": int(state.get("trial_used", 0) or 0),
        "activation_code": state.get("activation_code", ""),
        "token": state.get("token", ""),
        "expires_at": state.get("expires_at", ""),
        "ever_activated": bool(state.get("ever_activated", False)),
    }


def _signature(state):
    raw = json.dumps(_signature_payload(state),
                     sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(
        (raw + "|" + STATE_SIGNATURE_KEY).encode("utf-8")).hexdigest().upper()


def save_state(state):
    os.makedirs(_license_dir(), exist_ok=True)
    state = dict(state)
    state.update(
        {
            "product": PRODUCT_NAME,
            "plugin_code": PRODUCT_CODE,
            "fixed_code": FIXED_CODE,
            "application": APPLICATION_TYPE,
            "version": PRODUCT_VERSION,
            "device_id": device_id(),
            "device_name": device_name(),
        }
    )
    state["signature"] = _signature(state)
    temporary = _license_file() + ".tmp"
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(state, stream, indent=2, sort_keys=True)
    os.replace(temporary, _license_file())


def load_state():
    state = _default_state()
    if not os.path.isfile(_license_file()):
        return state
    try:
        with open(_license_file(), "r", encoding="utf-8") as stream:
            loaded = json.load(stream)
        if not isinstance(loaded, dict):
            raise ValueError("Invalid license object")
    except Exception:
        state.update(status="inactive", trial_used=TRIAL_LIMIT,
                     server_message="Local license data is invalid.")
        return state

    saved_signature = _text(loaded.pop("signature", "")).strip().upper()
    if _text(loaded.get("device_id", "")).strip().upper() not in ("", device_id()):
        state.update(status="inactive", trial_used=TRIAL_LIMIT,
                     server_message="The saved license belongs to another Device ID.")
        return state
    if saved_signature == _signature(loaded):
        state.update(loaded)
        return state

    state.update(
        status="unknown",
        trial_used=TRIAL_LIMIT,
        activation_code=_text(loaded.get(
            "activation_code", "")).strip().upper(),
        token=_text(loaded.get("token", "")).strip(),
        ever_activated=bool(loaded.get("ever_activated") or loaded.get(
            "activation_code") or loaded.get("token")),
        server_message="Local license data requires online revalidation.",
    )
    return state


def trial_remaining(state=None):
    state = state or load_state()
    return max(0, TRIAL_LIMIT - int(state.get("trial_used", 0) or 0))


def _normalise_code(value):
    return _text(value).strip().upper().replace(" ", "")


def _code_format_valid(value):
    value = _normalise_code(value)
    if not value:
        return True
    pattern = r"^{}-[0-9]{{4}}{}(?:-[A-Z0-9]+){{2,}}$".format(
        re.escape(PRODUCT_CODE), re.escape(FIXED_CODE)
    )
    return bool(re.match(pattern, value))


def _identity():
    return {
        "plugin_code": PRODUCT_CODE,
        "product_code": PRODUCT_CODE,
        "product": PRODUCT_CODE,
        "product_name": PRODUCT_NAME,
        "fixed_code": FIXED_CODE,
        "device_id": device_id(),
        "machine_id": device_id(),
        "machine_name": device_name(),
        "device_name": device_name(),
        "application": APPLICATION_TYPE,
        "app_type": APPLICATION_TYPE,
        "version": PRODUCT_VERSION,
    }


def request_page_url():
    return REQUEST_URL + "?" + urlencode(_identity())


def _response_dicts(value):
    if isinstance(value, dict):
        yield value
        for key in ("data", "license", "activation", "result", "payload"):
            child = value.get(key)
            if child is not None:
                yield from _response_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _response_dicts(child)


def _response_value(response, keys):
    for item in _response_dicts(response):
        for key in keys:
            value = item.get(key)
            if value not in (None, ""):
                return _text(value).strip()
    return ""


def _response_status(response):
    if has_denial(response):
        return "inactive"
    value = _response_value(
        response, ("status", "license_status", "activation_status", "state"))
    value = value.lower().replace("-", "_").replace(" ", "_")
    if value in (
        "active",
        "activated",
        "valid",
        "success",
        "successful",
        "approved",
        "aktif",
            "berhasil"):
        return "active"
    if value in (
        "inactive", "expired", "revoked", "blocked", "invalid", "rejected",
        "not_active", "false", "failed", "failure", "gagal", "tidak_aktif",
    ):
        return "inactive"

    positive_values = (
        True,
        1,
        "1",
        "true",
        "yes",
        "ok",
        "active",
        "activated",
        "valid",
        "success",
        "successful",
        "aktif",
        "berhasil")
    negative_values = (False, 0, "0", "false", "no", "inactive",
                       "invalid", "failed", "failure", "gagal", "tidak aktif")
    for item in _response_dicts(response):
        for key in ("active", "activated", "valid", "success"):
            flag = item.get(key)
            normalised = flag.strip().lower() if isinstance(flag, str) else flag
            if normalised in positive_values:
                return "active"
            if normalised in negative_values:
                return "inactive"

    # Some License Hub endpoints return only a human-readable message. Check
    # failure phrases first so text such as "tidak berhasil" is never accepted.
    message = _response_message(response, "").strip().lower()
    message = re.sub(r"\s+", " ", message)
    negative_phrases = (
        "tidak berhasil", "aktivasi gagal", "gagal", "tidak aktif",
        "tidak valid", "kedaluwarsa", "kadaluarsa", "ditolak", "dibatalkan",
        "activation failed", "not active", "not valid", "invalid", "expired",
        "revoked", "blocked", "rejected", "cancelled", "canceled",
    )
    if any(phrase in message for phrase in negative_phrases):
        return "inactive"
    positive_phrases = (
        "aktivasi berhasil", "berhasil diaktifkan", "berhasil diaktivasi",
        "lisensi aktif", "activation successful", "successfully activated",
        "license is active", "license active",
    )
    if any(phrase in message for phrase in positive_phrases):
        return "active"
    return "unknown"


def _response_message(response, fallback):
    return _response_value(
        response,
        ("message",
         "detail",
         "error",
         "reason",
         "description")) or fallback


def _post(url, payload, timeout=12):
    response, error = request_json(
        "POST",
        url,
        payload,
        timeout=timeout,
        user_agent="SpatialFormatConverter-QGIS/{}".format(PRODUCT_VERSION),
    )
    if response is None:
        raise LicenseError(error or "License Hub returned no response.")
    return response


def _try_requests(endpoints, payloads):
    errors = []
    for endpoint in endpoints:
        for payload in payloads:
            try:
                response = _post(endpoint, payload)
                if isinstance(response, (dict, list)):
                    return response, endpoint
            except Exception as error:
                errors.append(str(error))
    raise LicenseError(
        errors[-1] if errors else "No compatible server response.")


def _activation_payloads(code):
    common = _identity()
    payloads = []
    for key in ("activation_code", "license_key", "code", "key"):
        payload = dict(common)
        payload[key] = code
        if key == "activation_code":
            payload["license_key"] = code
        payloads.append(payload)
    return payloads


def _status_payloads(state):
    common = _identity()
    payloads = []
    code = _normalise_code(state.get("activation_code", ""))
    token = _text(state.get("token", "")).strip()
    if code:
        payload = dict(common, activation_code=code, license_key=code)
        payloads.append(payload)
    if token:
        payloads.append(dict(common, activation_token=token, token=token))
    payloads.append(common)
    return payloads


def _identity_matches(response, expected_code=""):
    product = _response_value(
        response, ("plugin_code", "product_code", "plugin", "product")).upper()
    if product and product not in (PRODUCT_CODE, PRODUCT_NAME.upper()):
        return False, "License Hub returned another product identity."
    remote_device = _response_value(
        response, ("device_id", "machine_id")).upper()
    if remote_device and remote_device != device_id():
        return False, "Activation belongs to another Device ID."
    remote_code = _normalise_code(_response_value(
        response, ("activation_code", "license_key", "code")))
    if remote_code and expected_code and remote_code != _normalise_code(expected_code):
        return False, "License Hub returned another activation identity."
    return True, ""


def _store_active(response, endpoint, activation_code=""):
    state = load_state()
    state.update(
        status="active",
        ever_activated=True,
        activation_code=_normalise_code(
            activation_code
            or _response_value(response, ("activation_code", "license_key", "code"))
            or state.get("activation_code", "")
        ),
        token=_response_value(response, ("activation_token", "token",
                              "license_token", "access_token")) or state.get("token", ""),
        expires_at=_response_value(
            response, ("expires", "expires_at", "expiry", "valid_until")) or state.get("expires_at", ""),
        last_check=_utc_now(),
        last_endpoint=endpoint,
        server_message=_response_message(
            response, "License status is active."),
    )
    save_state(state)
    return state


def activate(code):
    code = _normalise_code(code)
    if not code:
        return False, "Enter the activation data received from License Hub."
    if not _code_format_valid(code):
        return False, "The activation data format is not valid."
    try:
        response, endpoint = _try_requests(
            ACTIVATION_ENDPOINTS, _activation_payloads(code))
    except LicenseError as error:
        return False, "License Hub could not confirm activation: {}".format(error)
    valid, message = _identity_matches(response, code)
    if not valid:
        return False, message
    if _response_status(response) != "active":
        return False, _response_message(
            response, "Activation is not active for this Device ID.")
    _store_active(response, endpoint, code)
    return True, "Activation successful. Spatial Format Converter is Active."


def refresh():
    state = load_state()
    try:
        response, endpoint = _try_requests(
            STATUS_ENDPOINTS, _status_payloads(state))
    except LicenseError as error:
        return None, "License Hub could not be reached: {}".format(error), state
    valid, message = _identity_matches(
        response, state.get("activation_code", ""))
    if not valid:
        state.update(status="inactive", server_message=message,
                     last_check=_utc_now())
        save_state(state)
        return False, message, state
    if _response_status(response) == "active":
        state = _store_active(response, endpoint,
                              state.get("activation_code", ""))
        return True, state.get("server_message", "License is active."), state
    state.update(
        status="inactive",
        server_message=_response_message(
            response, "License is inactive or expired."),
        last_check=_utc_now(),
        last_endpoint=endpoint,
    )
    save_state(state)
    return False, state["server_message"], state


def access_status(check_online=False):
    state = load_state()
    if check_online:
        result, message, online_state = refresh()
        if result is True:
            return "active", message, online_state
        if result is False and (
            online_state.get("ever_activated")
            or online_state.get("activation_code")
            or online_state.get("token")
        ):
            return "inactive", message, online_state
        if result is None and str(state.get("status", "")).lower() == "active":
            return "inactive", (
                message
                or "The active license could not be verified online."
            ), state
    if str(state.get("status", "")).lower() == "active":
        return "active", "License status is active.", state
    if state.get("ever_activated") or state.get(
            "activation_code") or state.get("token"):
        return "inactive", state.get("server_message") or "License is inactive.", state
    remaining = trial_remaining(state)
    if remaining:
        return "trial", "Trial runs remaining: {}.".format(remaining), state
    return "inactive", "Trial expired. Activate Spatial Format Converter to continue.", state


def require_access():
    mode, message, state = access_status(check_online=True)
    if mode == "inactive":
        raise LicenseError(message)
    return mode, message


def record_success(access_mode):
    if access_mode != "trial":
        return
    state = load_state()
    state["trial_used"] = min(TRIAL_LIMIT, int(
        state.get("trial_used", 0) or 0) + 1)
    if state["trial_used"] >= TRIAL_LIMIT:
        state.update(
            status="inactive",
            server_message="Trial expired. Activate Spatial Format Converter to continue.")
    else:
        state["status"] = "trial"
    save_state(state)


def status_text(check_online=False):
    mode, message, _state = access_status(check_online=check_online)
    if mode == "active":
        return "ACTIVE — QGIS — Device ID: {}".format(device_id())
    if mode == "trial":
        return "TRIAL — {}".format(message)
    return "INACTIVE — {}".format(message)
