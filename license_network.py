# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Small HTTPS JSON client backed by QGIS' network manager.

The official QGIS plugin guidance recommends QgsNetworkAccessManager so proxy,
authentication, and certificate settings configured in QGIS are respected.
Only the Ruang Spasial License Hub HTTPS origin is accepted.
"""

import json
from urllib.parse import urlencode, urlparse

try:
    from qgis.PyQt.QtCore import QByteArray, QEventLoop, QTimer, QUrl
    from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest
    from qgis.core import QgsNetworkAccessManager
except ImportError:  # Enables syntax and unit checks outside QGIS.
    QByteArray = None
    QEventLoop = None
    QTimer = None
    QUrl = None
    QNetworkReply = None
    QNetworkRequest = None
    QgsNetworkAccessManager = None


ALLOWED_HOST = "aktivasi.ruangspasial.my.id"
MAX_RESPONSE_BYTES = 1024 * 1024


def is_allowed_url(url):
    """Return True only for the exact License Hub HTTPS origin."""
    try:
        parsed = urlparse(str(url))
    except (TypeError, ValueError):
        return False
    return parsed.scheme.lower() == "https" and parsed.hostname == ALLOWED_HOST


def _decode_json(raw):
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, (dict, list)) else None


def request_json(method, url, payload=None, timeout=10, user_agent="QGISPlugin"):
    """Send one JSON request and return ``(payload, error_message)``."""
    method = str(method or "POST").upper()
    payload = dict(payload or {})
    if method not in ("GET", "POST"):
        return None, "Unsupported License Hub request method."
    if method == "GET" and payload:
        separator = "&" if "?" in url else "?"
        url = url + separator + urlencode(payload)
    if not is_allowed_url(url):
        return None, "The license request was blocked because its URL is not allowed."
    if QgsNetworkAccessManager is None:
        return None, "QGIS network manager is not available."

    request = QNetworkRequest(QUrl(url))
    request.setRawHeader(QByteArray(b"Accept"),
                         QByteArray(b"application/json"))
    request.setRawHeader(
        QByteArray(b"User-Agent"),
        QByteArray(str(user_agent).encode("ascii", errors="ignore")),
    )
    if hasattr(QNetworkRequest, "RedirectPolicyAttribute") and hasattr(
        QNetworkRequest, "NoLessSafeRedirectPolicy"
    ):
        request.setAttribute(
            QNetworkRequest.RedirectPolicyAttribute,
            QNetworkRequest.NoLessSafeRedirectPolicy,
        )

    manager = QgsNetworkAccessManager.instance()
    if method == "GET":
        reply = manager.get(request)
    else:
        request.setHeader(QNetworkRequest.ContentTypeHeader,
                          "application/json")
        body = QByteArray(json.dumps(payload).encode("utf-8"))
        reply = manager.post(request, body)

    event_loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    reply.finished.connect(event_loop.quit)
    timer.timeout.connect(event_loop.quit)
    timer.start(max(1, int(float(timeout) * 1000)))
    event_loop.exec_()

    if not reply.isFinished():
        reply.abort()
        reply.deleteLater()
        return None, "License Hub did not respond before the timeout."

    final_url = reply.url().toString()
    raw_bytes = bytes(reply.readAll())
    error_code = reply.error()
    error_text = reply.errorString()
    reply.deleteLater()

    if not is_allowed_url(final_url):
        return None, "License Hub redirected the request to an untrusted URL."
    if len(raw_bytes) > MAX_RESPONSE_BYTES:
        return None, "License Hub returned an unexpectedly large response."

    raw = raw_bytes.decode("utf-8", errors="replace")
    parsed = _decode_json(raw)
    if parsed is not None:
        return parsed, None
    if QNetworkReply is not None and error_code != QNetworkReply.NoError:
        return None, "License Hub request failed: %s" % error_text
    return None, "License Hub returned an invalid JSON response."
