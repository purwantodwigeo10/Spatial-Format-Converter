# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded HTTPS License Hub requests using QGIS proxy/TLS settings."""
import json
from urllib.parse import urlencode, urlparse
from .qt_compat import run_dialog_or_loop
try:
    from qgis.PyQt.QtCore import QByteArray, QEventLoop, QTimer, QUrl
    from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest
    from qgis.core import QgsNetworkAccessManager
except ImportError:
    QgsNetworkAccessManager = None
ALLOWED_HOST = "aktivasi.ruangspasial.my.id"
MAX_RESPONSE_BYTES = 1024 * 1024

def is_allowed_url(url):
    try:
        p = urlparse(str(url))
        return (p.scheme.lower() == "https" and p.hostname == ALLOWED_HOST
                and p.port in (None, 443) and not p.username and not p.password)
    except (TypeError, ValueError):
        return False

def _decode_json(raw):
    try:
        result = json.loads(raw)
        return result if isinstance(result, (dict, list)) else None
    except (ValueError, TypeError):
        return None

def request_json(method, url, payload=None, timeout=10, user_agent="QGISPlugin"):
    method = str(method).upper()
    if method not in ("GET", "POST") or not is_allowed_url(url):
        return None, "License Hub request URL or method is not allowed."
    if QgsNetworkAccessManager is None:
        return None, "QGIS network manager is not available."
    if method == "GET" and payload:
        url += ("&" if "?" in url else "?") + urlencode(payload)
    request = QNetworkRequest(QUrl(url))
    request.setRawHeader(QByteArray(b"Accept"), QByteArray(b"application/json"))
    request.setRawHeader(QByteArray(b"User-Agent"), QByteArray(user_agent.encode("ascii", "ignore")))
    # Do not forward activation data to any redirected endpoint.
    request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                         QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
    manager = QgsNetworkAccessManager.instance()
    if method == "GET":
        reply = manager.get(request)
    else:
        request.setRawHeader(
            QByteArray(b"Content-Type"), QByteArray(b"application/json"))
        reply = manager.post(request, QByteArray(json.dumps(payload or {}).encode("utf-8")))
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    data = bytearray()
    too_large = [False]
    def drain():
        if too_large[0]:
            return
        while reply.bytesAvailable() > 0:
            chunk = bytes(reply.read(min(65536, MAX_RESPONSE_BYTES + 1 - len(data))))
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > MAX_RESPONSE_BYTES:
                too_large[0] = True
                reply.abort()
                loop.quit()
                break
    reply.readyRead.connect(drain)
    reply.finished.connect(loop.quit)
    timer.timeout.connect(loop.quit)
    timer.start(max(1, int(float(timeout) * 1000)))
    if not reply.isFinished():
        run_dialog_or_loop(loop)
    timer.stop()
    try:
        if too_large[0]:
            return None, "License Hub response exceeded the size limit."
        if not reply.isFinished():
            reply.abort()
            return None, "License Hub did not respond before the timeout."
        drain()
        if too_large[0]:
            return None, "License Hub response exceeded the size limit."
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if status is None or not 200 <= int(status) < 300:
            return None, "License Hub returned HTTP %s." % status
        if reply.error() != QNetworkReply.NetworkError.NoError:
            return None, "License Hub request failed: %s" % reply.errorString()
        if not is_allowed_url(reply.url().toString()):
            return None, "License Hub response came from an untrusted URL."
        parsed = _decode_json(bytes(data).decode("utf-8", "replace"))
        if parsed is None:
            return None, "License Hub returned an invalid JSON response."
        return parsed, None
    finally:
        reply.deleteLater()
