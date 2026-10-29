import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

SAMPLE = (Path(__file__).resolve().parent / 'sample.js').read_text(encoding='utf-8-sig')
ROLES = {'main', 'same', 'cross', 'nested-return', 'srcdoc', 'about-blank'}


def document(role, children=''):
    if role not in ROLES:
        raise ValueError('Unknown owned fixture role')
    return ('<!doctype html><html data-role="' + role + '"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Owned first-script screen fixture</title><script>' + SAMPLE + '</script>'
            '<style>body{margin:0;padding-top:64px}iframe{display:block;width:320px;'
            'height:140px;border:0;margin:8px}button{position:fixed;left:16px;top:24px;'
            'width:72px;height:28px;z-index:2}html[data-role=main] body{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}html[data-role=cross] iframe{height:64px;width:260px;margin:0}@media(max-width:600px){html[data-role=main] body{grid-template-columns:1fr}}</style></head><body>'
            '<button id="probe">Click probe</button>' + children + '</body></html>')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        request = urlsplit(self.path)
        values = parse_qs(request.query)
        role = values.get('role', ['main'])[0]
        if request.path != '/screen' or role not in ROLES:
            self.send_error(404)
            return
        port = self.server.server_port
        children = ''
        if role == 'main':
            srcdoc = html.escape(document('srcdoc'), quote=True)
            children = (f'<iframe name="same" src="http://127.0.0.1:{port}/screen?role=same"></iframe>'
                        f'<iframe name="cross" src="http://localhost:{port}/screen?role=cross"></iframe>'
                        f'<iframe name="srcdoc" srcdoc="{srcdoc}"></iframe>'
                        '<iframe name="about-blank"></iframe>')
            # The blank frame gets its first script through ordinary document.write,
            # not an addInitScript/API replacement injected by the automation driver.
            import json
            contents = json.dumps(document('about-blank')).replace('<', chr(92) + 'u003c')
            children += ('<script>const d=document.querySelector(\'iframe[name="about-blank"]\').contentDocument;'
                         'd.open();d.write(' + contents + ');d.close();</script>')
        elif role == 'cross':
            children = f'<iframe name="nested-return" src="http://127.0.0.1:{port}/screen?role=nested-return"></iframe>'
        body = document(role, children).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)


def create_server():
    return ThreadingHTTPServer(('127.0.0.1', 0), Handler)
