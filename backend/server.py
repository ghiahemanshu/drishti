"""Loopback-only HTTP API + production SPA host. Python 3.11+, no pip packages."""
import argparse, json, secrets, threading, traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, unquote
from .store import Store, AppError, ROOT

class Handler(SimpleHTTPRequestHandler):
    store: Store
    session_token = secrets.token_urlsafe(32)
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(ROOT/'dist'),**kwargs)
    def log_message(self,format,*args): pass
    def end_headers(self):
        self.send_header('X-Content-Type-Options','nosniff'); self.send_header('X-Frame-Options','DENY'); self.send_header('Referrer-Policy','no-referrer'); self.send_header('Cache-Control','no-store')
        super().end_headers()
    def local_host(self): return self.headers.get('Host','').split(':')[0] in ('127.0.0.1','localhost')
    def send_json(self,status,value):
        data=json.dumps(value,allow_nan=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        if not self.local_host(): return self.send_json(403,{'error':'Only localhost requests are allowed.'})
        path=urlsplit(self.path).path
        try:
            if path=='/api/state': return self.send_json(200,{**self.store.snapshot(),'sessionToken':self.session_token})
            if path=='/api/health': return self.send_json(200,{'ok':True,'mode':'simulation'})
            if path.startswith('/api/security/'): return self.send_json(200,self.store.security(unquote(path[len('/api/security/'):])))
            if path.startswith('/api/'): return self.send_json(404,{'error':'API endpoint not found.'})
            if path=='/' and not (ROOT/'dist'/'index.html').exists(): return self.send_json(503,{'error':'Frontend build missing. Run npm install && npm run build.'})
            return super().do_GET()
        except AppError as e: return self.send_json(e.status,{'error':e.message})
        except Exception: traceback.print_exc(); return self.send_json(500,{'error':'Unexpected server error. See the local server log.'})
    def do_POST(self):
        if not self.local_host(): return self.send_json(403,{'error':'Only localhost requests are allowed.'})
        if not secrets.compare_digest(self.headers.get('X-Session-Token',''),self.session_token): return self.send_json(403,{'error':'Refresh the app before making changes.'})
        origin=self.headers.get('Origin')
        if origin and origin not in ('http://127.0.0.1:8765','http://localhost:8765','http://127.0.0.1:5173','http://localhost:5173',f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'):
            return self.send_json(403,{'error':'Request origin is not allowed.'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=100000: raise AppError('Request must be between 1 and 100,000 bytes.')
            if self.headers.get('Content-Type','').split(';')[0]!='application/json': raise AppError('Send JSON.',415)
            def invalid_constant(value): raise ValueError('Non-finite JSON number.')
            body=json.loads(self.rfile.read(length),parse_constant=invalid_constant)
            if not isinstance(body,dict): raise AppError('Request must be a JSON object.')
            path=urlsplit(self.path).path
            if path=='/api/scan': result=self.store.scan()
            elif path=='/api/rules': result=self.store.save_rule(body)
            elif path=='/api/thesis': result=self.store.save_thesis(body.get('isin'),body.get('body'))
            elif path=='/api/alerts/review': result=self.store.acknowledge(body.get('alertId'))
            elif path=='/api/orders/preview': result=self.store.preview(body)
            elif path=='/api/orders/confirm': result=self.store.confirm(body)
            else: raise AppError('API endpoint not found.',404)
            return self.send_json(200,result)
        except AppError as e: return self.send_json(e.status,{'error':e.message})
        except (ValueError,TypeError,KeyError) as e: return self.send_json(400,{'error':f'Invalid request: {e}'})
        except Exception: traceback.print_exc(); return self.send_json(500,{'error':'Unexpected server error. No uncommitted changes were saved.'})

def run():
    parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=8765); parser.add_argument('--db'); args=parser.parse_args()
    Handler.store=Store(args.db); server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler); stopped=threading.Event()
    def monitor():
        while not stopped.wait(60):
            try: Handler.store.scan(manual=False)
            except Exception: traceback.print_exc()
    threading.Thread(target=monitor,daemon=True).start()
    print(f'Drishti simulation ready: http://127.0.0.1:{args.port}',flush=True)
    print('Fictional data only. No live broker calls. Re-evaluates every 60 seconds.',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: stopped.set(); server.server_close()

if __name__=='__main__': run()
