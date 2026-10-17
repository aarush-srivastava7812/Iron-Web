import json
from functools import partial
from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
directory=Path(__file__).resolve().parent
server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(directory)))
(directory/'server.json').write_text(json.dumps({'url':f'http://127.0.0.1:{server.server_port}/index.html'}))
server.serve_forever()
