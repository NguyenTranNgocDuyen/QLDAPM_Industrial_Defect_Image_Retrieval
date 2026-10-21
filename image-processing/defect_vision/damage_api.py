"""Small persistent HTTP worker. Java owns public multipart uploads and history.

Start: python -m defect_vision.damage_api --port 8000
Wire request: POST /analyze, binary image bytes; surface, aspect and complete query.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import socket
from urllib.parse import parse_qs, urlparse
import re

from .damage_service import DamageWorker


class DamageHTTPServer(ThreadingHTTPServer):
    # SO_REUSEADDR on Windows can permit two workers to bind the same address,
    # leaving requests handled by an old process after a restart.
    allow_reuse_address = os.name != 'nt'

    def server_bind(self):
        if os.name == 'nt':
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def make_handler(worker):
    class Handler(BaseHTTPRequestHandler):
        def send_json(self, status, value):
            body = json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == '/health':
                return self.send_json(200, dict(status='ready', detector_loaded_in_damage_engine=False,
                    threshold=worker.engine.threshold, inference_variant=worker.engine.variant,
                    severity_config_version=worker.config['version'],
                    classification_rule=worker.config.get('classification', {}).get('rule', 'max_metric'),
                    corner_config_version=worker.corner_config['version'],
                    requests_processed=worker.requests_processed, detector_calls=worker.detector_calls))
            match = re.fullmatch(r'/api/damage-assets/([0-9a-f-]{36})/([a-z_]+\.png)', path)
            if match:
                file = worker.output / match[1] / match[2]
                if file.is_file():
                    content = file.read_bytes()
                    self.send_response(200)
                    self.send_header('Content-Type', 'image/png')
                    self.send_header('Content-Length', str(len(content)))
                    self.end_headers()
                    return self.wfile.write(content)
            self.send_json(404, dict(error='not_found'))

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path != '/analyze':
                return self.send_json(404, dict(error='not_found'))
            try:
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 25 * 1024 * 1024:
                    return self.send_json(413, dict(status='insufficient_evidence', error='invalid_upload_size'))
                query = parse_qs(parsed.query)
                aspect = query.get('aspect', [None])[0]
                result = worker.analyze(self.rfile.read(length), surface=query.get('surface', ['unknown'])[0],
                    surface_aspect_ratio=float(aspect) if aspect is not None else None,
                    full_surface_confirmed=query.get('complete', ['false'])[0] == 'true')
                self.send_json(200, result)
            except Exception as exc:
                self.send_json(422, dict(status='insufficient_evidence', needs_review=True,
                    error=f'{type(exc).__name__}: {exc}', estimated_severity=None))
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--device', default=None)
    args = parser.parse_args()
    # Fail startup on missing/corrupt weights. No fake healthy fallback.
    worker = DamageWorker(device=args.device)
    server = DamageHTTPServer((args.host, args.port), make_handler(worker))
    print(f'Phone damage worker ready at http://{args.host}:{args.port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
