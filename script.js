from http.server import BaseHTTPRequestHandler
import json
class handler(BaseHTTPRequestHandler):
def do_GET(self):
self.send_response(200)
self.send_header('Content-type', 'application/json; charset=utf-8')
self.send_header('Access-Control-Allow-Origin', '*')
self.end_headers()
try:
with open('data.json', 'r', encoding='utf-8') as f:
db_data = json.load(f)
except Exception:
db_data = []
self.wfile.write(json.dumps(db_data, ensure_ascii=False).encode('utf-8'))
return
