"""Loopback server for the audit dashboard and declarative JSON/CSV execution."""
import json
import sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
from audit import run_bundle

WEB = Path(__file__).resolve().parents[2] / 'carbon-provenance-lab' / 'dist'
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def reply(self, code, payload):
        data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def allowed(self):
        host = self.headers.get('Host', '')
        return host in {f'127.0.0.1:{PORT}', f'localhost:{PORT}'}

    def do_GET(self):
        if not self.allowed():
            return self.reply(403, {'error': 'Host not permitted'})
        if self.path == '/api/health':
            return self.reply(200, {'execution': True, 'engine': 'AuditLedger', 'schema_version': 1})
        super().do_GET()

    def do_POST(self):
        origin = self.headers.get('Origin')
        if not self.allowed() or (origin and origin not in {f'http://127.0.0.1:{PORT}', f'http://localhost:{PORT}'}):
            return self.reply(403, {'error': 'Origin not permitted'})
        if self.path != '/api/run':
            return self.reply(404, {'error': 'Route not found'})
        try:
            n = int(self.headers.get('Content-Length', 0))
            if not 0 < n <= 10 * 1024 * 1024:
                return self.reply(413, {'error': 'Each plan must be no larger than 10 MB'})
            bundle = json.loads(self.rfile.read(n))
            result = run_bundle(bundle)
            return self.reply(200, result)
        except (ValueError, KeyError, TypeError, IndexError, OverflowError) as exc:
            return self.reply(400, {'error': str(exc)})

if __name__ == '__main__':
    print(f'Local: http://127.0.0.1:{PORT}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
