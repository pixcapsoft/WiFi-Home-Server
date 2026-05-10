"""
http_serve.py
─────────────
Standalone HTTP file server extracted from WiFi-Home-Server.
Hosts local files/folders over WiFi so any device on the same
network can browse and download them through a browser.
No ADB, no USB, no app needed on the Android side.
Android just opens: http://<PC_IP>:8765

How it works:
1. get_local_ip()            — finds this PC's WiFi IP
2. build_index_html()        — generates the root HTML listing all shared items
3. build_dir_html()          — generates HTML for browsing inside a folder
4. serve_file()              — streams a file to the client for download
5. make_handler()            — creates the HTTP request handler class bound to your file roots
6. start_server()            — starts the server (blocking)
7. start_server_background() — starts the server in a background thread (non-blocking)

Usage example at the bottom of this file.
"""

import html
import os
import socket
import threading
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING HELPER
# ─────────────────────────────────────────────────────────────────────────────

LOG_CALLBACK = None
CONNECTION_CALLBACK = None


def _log(level: str, msg: str):
    """
    If LOG_CALLBACK is set, route messages to it (e.g., for a GUI).
    Otherwise, standard print.
    """
    if LOG_CALLBACK:
        LOG_CALLBACK(level, msg)
    else:
        print(msg)


def _conn(action: str):
    """Notify GUI when a connection starts or ends. action='connect'|'disconnect'"""
    if CONNECTION_CALLBACK:
        CONNECTION_CALLBACK(action)


# ─────────────────────────────────────────────────────────────────────────────
# NETWORK HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_local_ip() -> str:
    """
    Find this machine's local network IP address (e.g. 192.168.1.42).
    It works by opening a dummy UDP socket toward a public DNS server.
    No actual data is sent — the OS just picks the right local interface
    to route through, and we read that interface's IP.
    Returns "127.0.0.1" as fallback if detection fails.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))  # doesn't actually send anything
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        return "127.0.0.1"


def format_size(size_bytes: int) -> str:
    """
    Convert a byte count into a human-readable string.
    e.g. 1048576 → "1.0 MB"
    """
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


# ─────────────────────────────────────────────────────────────────────────────
# SECURITY HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _safe_join(root: str, rel_path: str) -> str | None:
    """
    Safely join a root directory with a relative path, resolving all symlinks
    and ensuring the result stays inside the root.

    FIX #1 — Path traversal via startswith() prefix bypass:
        The old code used full_path.startswith(root), which is a string prefix
        check, not a path boundary check. A root of '/data/share' would
        incorrectly allow '/data/shareother/secret.txt' to pass.
        We now append os.sep so the boundary is exact.

    FIX #2 — Symlink traversal:
        os.path.normpath() collapses '..' but does NOT follow symlinks.
        A symlink inside the shared folder pointing to '/etc/passwd' would
        have bypassed the old check. We now use os.path.realpath() which
        fully resolves symlinks before comparing.

    Returns the resolved absolute path string if safe, or None if the path
    escapes the root (which the caller should treat as a 404).
    """
    # Resolve the root itself (may also contain symlinks)
    real_root = os.path.realpath(root)

    if rel_path:
        candidate = os.path.realpath(os.path.join(real_root, rel_path))
    else:
        candidate = real_root

    # Ensure the candidate is either the root itself or strictly inside it.
    # We append os.sep so '/data/share' cannot match '/data/shareother/…'.
    root_prefix = real_root + os.sep
    if candidate != real_root and not candidate.startswith(root_prefix):
        return None  # Escape attempt — caller returns 404

    return candidate


def _safe_filename_header(filename: str) -> str:
    """
    Build a safe Content-Disposition header value for the given filename.

    FIX #4 — Content-Disposition header injection:
        The old code embedded the raw filename inside double-quotes:
            attachment; filename="<raw name>"
        A filename containing '"' or newline characters could break the header
        or inject arbitrary HTTP headers.

        We now produce two tokens per RFC 6266 / RFC 5987:
        - 'filename' with ASCII-safe fallback (non-ASCII and special chars stripped)
        - 'filename*' with full UTF-8 percent-encoded value (RFC 5987)

        This keeps maximum compatibility across browsers while being injection-safe.
    """
    # ASCII-safe fallback: keep only printable ASCII, strip quotes and slashes
    ascii_name = "".join(
        c for c in filename
        if 32 <= ord(c) < 127 and c not in ('"', "'", '\\', '/', '\r', '\n')
    ) or "download"

    # RFC 5987 encoded value: UTF-8 percent-encode everything except unreserved chars
    encoded_name = urllib.parse.quote(filename, safe="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")

    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{encoded_name}'


# ─────────────────────────────────────────────────────────────────────────────
# HTML BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def html_shell(title: str, body: str) -> str:
    """
    Wraps any HTML body content in a full page with a dark stylesheet.
    Used by both the root index and directory listings.

    FIX #3 (partial) — The title is HTML-escaped here to prevent XSS when
    a directory path is embedded in the <title> tag.

    Args:
        title: shown in the browser tab (will be HTML-escaped)
        body:  the inner HTML to embed (must already be safe — see callers)

    Returns the full HTML string (UTF-8 safe).
    """
    safe_title = html.escape(title)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title} — WiFi-Home-Server</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: system-ui, sans-serif;
      background: #0f0f0f;
      color: #e0e0e0;
      padding: 28px 20px;
      max-width: 720px;
      margin: 0 auto;
    }}
    h1 {{ font-size: 1.4rem; color: #00c9e0; margin-bottom: 6px; }}
    p.sub {{ color: #555; font-size: 0.85rem; margin-bottom: 24px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{
      text-align: left; padding: 8px 10px;
      font-size: 0.75rem; text-transform: uppercase;
      color: #444; border-bottom: 1px solid #222;
    }}
    td {{ padding: 10px; border-bottom: 1px solid #1a1a1a; }}
    td a {{ color: #7ecfdf; text-decoration: none; }}
    td a:hover {{ text-decoration: underline; }}
    .size {{ color: #555; font-size: 0.85rem; text-align: right; }}
    .badge {{
      display: inline-block; padding: 2px 7px; border-radius: 4px;
      font-size: 0.7rem; font-weight: bold;
      background: #001a1f; color: #00c9e0;
    }}
  </style>
</head>
<body>{body}</body>
</html>"""


def build_index_html(roots: list[dict]) -> str:
    """
    Build the root page HTML that lists all shared files/folders.

    FIX #3 — Stored XSS via unescaped filenames:
        The old code embedded raw filenames and hrefs directly into HTML.
        Any file named e.g. '<script>alert(1)</script>.txt' would execute
        JavaScript in the browser.
        All user-controlled values (names, hrefs) are now passed through
        html.escape() before being placed in HTML context.

    Args:
        roots: list of sync-pair dicts (from WiFi-Home-Server config)

    Returns full HTML string.
    """
    rows = ""
    for pair in roots:
        local = pair["local"]
        name = os.path.basename(local.rstrip("/\\")) or local
        is_dir = os.path.isdir(local)
        icon = "📁" if is_dir else "📄"

        # URL-encode for the href, HTML-escape for display text
        href = html.escape("/" + urllib.parse.quote(name))
        safe_name = html.escape(name)
        size = "" if is_dir else html.escape(format_size(os.path.getsize(local)))

        rows += f"""
      <tr>
        <td>{icon} <a href="{href}">{safe_name}</a></td>
        <td class="size">{size}</td>
      </tr>"""

    body = f"""
  <h1>📡 WiFi-Home-Server File Server</h1>
  <p class="sub">Open a file to download it, or tap a folder to browse.</p>
  <table>
    <tr><th>Name</th><th style="text-align:right">Size</th></tr>
    {rows}
  </table>"""
    return html_shell("WiFi-Home-Server", body)


def build_dir_html(full_path: str, url_path: str) -> str:
    """
    Build a directory listing page for browsing inside a shared folder.
    Shows all files and subfolders sorted: folders first, then files.
    Includes a ".." back link (except at root).

    FIX #3 — Stored XSS via unescaped filenames (continued):
        All filenames and hrefs rendered into the page are now HTML-escaped.
        The back-link parent path is also escaped.

    Args:
        full_path: absolute local path to the directory being listed
        url_path:  the URL path (used to build links and the back button)

    Returns full HTML string.
    """
    try:
        entries = sorted(
            os.scandir(full_path),
            key=lambda e: (not e.is_dir(), e.name.lower())  # folders first
        )
    except PermissionError:
        return html_shell("Error", "<h1>Permission denied</h1>")

    rows = ""

    # Back link — strip last segment from url_path
    if "/" in url_path.strip("/"):
        parent = "/" + "/".join(url_path.strip("/").split("/")[:-1])
    else:
        parent = "/"

    safe_parent = html.escape(parent)
    rows += f'<tr><td><a href="{safe_parent}">⬆ ..</a></td><td class="size"></td></tr>'

    for entry in entries:
        icon = "📁" if entry.is_dir() else "📄"

        # Build a URL-safe href and separately HTML-escape the display name
        raw_href = f"/{url_path.strip('/')}/{urllib.parse.quote(entry.name)}"
        href = html.escape(raw_href)
        safe_entry_name = html.escape(entry.name)
        size = "" if entry.is_dir() else html.escape(format_size(entry.stat().st_size))

        rows += f"""
      <tr>
        <td>{icon} <a href="{href}">{safe_entry_name}</a></td>
        <td class="size">{size}</td>
      </tr>"""

    safe_url_path = html.escape(url_path.strip('/'))
    body = f"""
  <h1>📁 /{safe_url_path}</h1>
  <p class="sub"><a href="/" style="color:#555">← root</a></p>
  <table>
    <tr><th>Name</th><th style="text-align:right">Size</th></tr>
    {rows}
  </table>"""
    return html_shell(url_path, body)


# ─────────────────────────────────────────────────────────────────────────────
# FILE STREAMING
# ─────────────────────────────────────────────────────────────────────────────

def serve_file(handler: BaseHTTPRequestHandler, full_path: str):
    """
    Stream a local file to the HTTP client as a binary download.

    FIX #4 — Content-Disposition header injection:
        The filename is now passed through _safe_filename_header() which
        produces a properly encoded RFC 6266 / RFC 5987 header value instead
        of naively embedding the raw filename inside double-quotes.

    Reads in 64 KB chunks to avoid loading large files into memory.

    Args:
        handler:   the active BaseHTTPRequestHandler instance
        full_path: absolute local path to the file to send
    """
    try:
        file_size = os.path.getsize(full_path)
        filename = os.path.basename(full_path)

        handler.send_response(200)
        handler.send_header("Content-Type", "application/octet-stream")
        handler.send_header(
            "Content-Disposition",
            _safe_filename_header(filename)   # FIX #4
        )
        handler.send_header("Content-Length", str(file_size))
        handler.end_headers()

        # Stream in chunks — safe for large APKs, ZIPs, videos, etc.
        with open(full_path, "rb") as f:
            while True:
                chunk = f.read(65536)  # 64 KB per read
                if not chunk:
                    break
                handler.wfile.write(chunk)

        _log("info", f" [SENT] {filename} ({format_size(file_size)})")

    except (BrokenPipeError, ConnectionResetError):
        # Client disconnected mid-download — not an error, just ignore
        pass
    except Exception as e:
        _log("error", f" [ERR] Failed to serve {full_path}: {e}")


def send_html(handler: BaseHTTPRequestHandler, html_str: str, status: int = 200):
    """
    Send an HTML string response to the client.

    Args:
        handler:  active request handler
        html_str: the full HTML string to send
        status:   HTTP status code (default 200)
    """
    data = html_str.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def send_404(handler: BaseHTTPRequestHandler):
    """Send a simple 404 Not Found response."""
    send_html(handler, html_shell("Not Found", "<h1>404 — Not Found</h1>"), 404)


# ─────────────────────────────────────────────────────────────────────────────
# REQUEST HANDLER FACTORY
# ─────────────────────────────────────────────────────────────────────────────

def make_handler(roots: list[dict]) -> type:
    """
    Create and return an HTTP request handler class bound to `roots`.

    The returned class handles GET requests only:
        GET /            → root index listing all shared items
        GET /FolderName  → directory browser for that folder
        GET /Folder/file → file download
        anything else    → 404

    Args:
        roots: list of sync-pair dicts, each with a "local" key

    Returns:
        A class (not an instance) that HTTPServer can use.
    """

    class Handler(BaseHTTPRequestHandler):
        # Silence the default per-request log lines (we print our own)
        def log_message(self, format, *args):
            pass

        def do_GET(self):
            _conn("connect")
            try:
                # Decode %20 etc. from the URL path
                url_path = urllib.parse.unquote(self.path.lstrip("/"))

                # ── Root: list all shared items ──────────────────────────────
                if not url_path:
                    send_html(self, build_index_html(roots))
                    return

                # ── Resolve the URL path against our shared roots ────────────
                # The first segment of the URL is the item name (file or folder).
                # e.g. URL "/MyApp/output/app.apk" → root named "MyApp" + rel path "output/app.apk"
                segments = url_path.split("/", 1)
                root_name = segments[0]
                rel_path = segments[1] if len(segments) > 1 else ""

                # Find which root this name belongs to
                matched_root = None
                for pair in roots:
                    name = os.path.basename(pair["local"].rstrip("/\\"))
                    if name == root_name:
                        matched_root = pair["local"]
                        break

                if matched_root is None:
                    send_404(self)
                    return

                # FIX #1 & #2 — Use _safe_join() instead of os.path.join +
                # a naive startswith() check.  _safe_join() calls realpath()
                # to resolve all symlinks and uses an os.sep-terminated prefix
                # comparison so directory-boundary bypasses are impossible.
                full_path = _safe_join(matched_root, rel_path)

                if full_path is None:
                    # Path tried to escape the shared root — treat as 404
                    _log("warning", f" [WARN] Blocked path traversal attempt: {rel_path!r}")
                    send_404(self)
                    return

                if not os.path.exists(full_path):
                    send_404(self)
                    return

                if os.path.isdir(full_path):
                    send_html(self, build_dir_html(full_path, url_path))
                else:
                    serve_file(self, full_path)

            finally:
                _conn("disconnect")

    return Handler


# ─────────────────────────────────────────────────────────────────────────────
# SERVER STARTUP
# ─────────────────────────────────────────────────────────────────────────────

def start_server(roots: list[dict], port: int = 8765):
    """
    Start the HTTP file server and block until Ctrl+C.

    Args:
        roots: list of sync-pair dicts to serve
        port:  port to listen on (default 8765)
    """
    handler_class = make_handler(roots)
    server = HTTPServer(("0.0.0.0", port), handler_class)  # 0.0.0.0 = all interfaces
    ip = get_local_ip()
    _log("info", f"\n WiFi-Home-Server HTTP Server running")
    _log("info", f" Open on Android: http://{ip}:{port}\n")
    _log("info", " Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _log("warning", "\n Server stopped.")
        server.server_close()


def start_server_background(roots: list[dict], port: int = 8765) -> HTTPServer:
    """
    Start the HTTP file server in a background daemon thread (non-blocking).

    The thread is a daemon, so it dies automatically when the main program exits.

    Args:
        roots: list of sync-pair dicts to serve
        port:  port to listen on

    Returns:
        The HTTPServer instance — call server.shutdown() to stop it later.
    """
    handler_class = make_handler(roots)
    server = HTTPServer(("0.0.0.0", port), handler_class)
    ip = get_local_ip()
    _log("info", f" HTTP server running at http://{ip}:{port}")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server  # caller can call server.shutdown() to stop
