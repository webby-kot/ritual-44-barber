"""Local request-management prototype. Python 3.11+, no dependencies."""
import os, json, sqlite3, secrets, hmac, urllib.request, smtplib
from pathlib import Path
from datetime import date, datetime, timezone
from email.message import EmailMessage
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get('BOOKING_DB', str(ROOT / 'private' / 'bookings.sqlite')))
DB.parent.mkdir(parents=True, exist_ok=True)
TOKEN = os.environ.get('ADMIN_TOKEN') or secrets.token_urlsafe(32)
SERVICES = ['Ritual Cut — €25', 'Cut + Beard — €36', 'Beard Ritual — €19', 'Buzz / Clean — €18']
BARBERS = ['Anyone available', 'Marek K.', 'Denis N.', 'Tomáš V.']
with sqlite3.connect(DB) as conn:
    conn.execute('CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, created TEXT, data TEXT, status TEXT, delivery TEXT)')

def notify(data, reference):
    message = f"RITUAL 44 / {reference}\n" + '\n'.join(f'{k}: {v}' for k,v in data.items())
    results = {}
    channels = os.environ.get('NOTIFY_CHANNELS', '').split(',')
    for channel in ['email', 'telegram']:
        results[channel] = 'not_configured'
        if channel not in channels:
            continue
        try:
            if channel == 'telegram':
                token, chat = os.environ['TELEGRAM_BOT_TOKEN'], os.environ['TELEGRAM_CHAT_ID']
                req = urllib.request.Request('https://api.telegram.org/bot' + token + '/sendMessage', data=json.dumps({'chat_id':chat,'text':message}).encode(), headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    if not json.load(response).get('ok'): raise ValueError('Delivery failed')
            else:
                mail = EmailMessage()
                mail['From'], mail['To'] = os.environ['MAIL_FROM'], os.environ['MAIL_TO']
                mail['Subject'] = 'New appointment request / ' + reference
                mail.set_content(message)
                with smtplib.SMTP_SSL(os.environ['SMTP_HOST'], int(os.environ.get('SMTP_PORT','465')), timeout=10) as smtp:
                    smtp.login(os.environ['SMTP_USER'], os.environ['SMTP_PASSWORD'])
                    smtp.send_message(mail)
            results[channel] = 'sent'
        except Exception:
            results[channel] = 'failed'
    return results

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs): super().__init__(*args, directory=str(ROOT), **kwargs)
    def log_message(self, *args): pass
    def reply(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def authorized(self):
        return hmac.compare_digest(self.headers.get('Authorization',''), 'Bearer ' + TOKEN)
    def do_GET(self):
        path = self.path.split('?')[0]
        if path == '/api/requests':
            if not self.authorized(): return self.reply(401, {'error':'Invalid admin key.'})
            with sqlite3.connect(DB) as conn:
                rows = conn.execute('SELECT * FROM requests ORDER BY created DESC LIMIT 500').fetchall()
            return self.reply(200, [{'id':r[0],'created':r[1],**json.loads(r[2]),'status':r[3],'delivery':json.loads(r[4])} for r in rows])
        if path == '/api/config':
            return self.reply(200, {'mode':'local-prototype','channels':os.environ.get('NOTIFY_CHANNELS','')})
        if path not in ['/', '/index.html','/styles.css','/script.js','/admin.html','/admin.js'] and not (path.startswith('/assets/') and '..' not in path and '%' not in path):
            return self.reply(404, {'error':'Not found'})
        super().do_GET()
    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length',0))
            if not 0 < length <= 8192: return self.reply(400, {'error':'Invalid request size.'})
            data = json.loads(self.rfile.read(length))
            if not isinstance(data,dict): raise ValueError()
        except (ValueError, TypeError): return self.reply(400, {'error':'Invalid request.'})
        if self.path == '/api/status':
            if not self.authorized(): return self.reply(401, {'error':'Invalid admin key.'})
            if data.get('status') not in ['new','confirmed','cancelled']: return self.reply(400, {'error':'Invalid status.'})
            with sqlite3.connect(DB) as conn:
                changed = conn.execute('UPDATE requests SET status=? WHERE id=?', (data['status'],data.get('id'))).rowcount
            return self.reply(200 if changed else 404, {'ok':bool(changed)})
        if self.path != '/api/requests': return self.reply(404, {'error':'Not found'})
        fields = ['name','phone','service','barber','day','time','message']
        clean = {k:str(data.get(k,'')).strip() for k in fields}
        try:
            day = date.fromisoformat(clean['day'])
            valid_time = datetime.strptime(clean['time'], '%H:%M').time()
            valid = (date.today() <= day and day.weekday() != 6 and 9 <= valid_time.hour < (16 if day.weekday()==5 else 20))
        except ValueError: valid = False
        if not valid or not 2 <= len(clean['name']) <= 80 or not 7 <= len(clean['phone']) <= 30 or clean['service'] not in SERVICES or clean['barber'] not in BARBERS or len(clean['message']) > 1000:
            return self.reply(400, {'error':'Check your details. Choose a future date, Monday–Saturday, within opening hours.'})
        reference = secrets.token_hex(6).upper()
        with sqlite3.connect(DB) as conn:
            conn.execute('INSERT INTO requests VALUES (?,?,?,?,?)',(reference,datetime.now(timezone.utc).isoformat(),json.dumps(clean),'new','{}'))
        delivery = notify(clean, reference)
        with sqlite3.connect(DB) as conn:
            conn.execute('UPDATE requests SET delivery=? WHERE id=?',(json.dumps(delivery),reference))
        self.reply(201, {'id':reference,'status':'new'})

if __name__ == '__main__':
    print('Local preview: http://127.0.0.1:8844', flush=True)
    print('Admin key is saved locally in private/admin-key.txt. Do not publish it.', flush=True)
    (DB.parent / 'admin-key.txt').write_text(TOKEN)
    ThreadingHTTPServer(('127.0.0.1',8844),Handler).serve_forever()
