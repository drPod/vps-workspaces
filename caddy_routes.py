"""Generate Caddy routes and standard systemd socket proxies for saved localhost apps."""
import hashlib
from pathlib import Path
import subprocess
from urllib.parse import urlsplit
from model import surfaces, local_browser, browser_host, origin


def preview_id(surface):
    return hashlib.sha256(origin(surface['url']).encode()).hexdigest()[:10]


AUTH = '''forward_auth unix//srv/vps-workspaces.sock {
 uri /auth
 header_up X-VWS-Upgrade {http.request.header.Upgrade}
}'''
STRIP = '''header_up -Authorization
header_up -Referer
header_up Cookie "(^|; *)vws_access=[^;]*" ""'''


def render(documents):
    blocks = []
    for doc in documents:
        name = doc['id']
        blocks.append(f'''{doc['host']} {{
 route {{
  @ide path /ide /ide/*
  handle @ide {{
   {AUTH}
   uri strip_prefix /ide
   reverse_proxy unix//srv/vws-ide-{name}.sock {{
    {STRIP}
    header_up Host localhost
    header_down Location "^/(.*)$" "/ide/${{1}}"
   }}
  }}
  redir /classic/ /ide/ 302
  handle {{
   reverse_proxy unix//srv/vps-workspaces.sock
  }}
 }}
}}''')
        seen = set()
        for s in surfaces(doc['layout']):
            if s['type'] != 'browser' or not local_browser(s):
                continue
            host = browser_host(doc, s)
            if host in seen:
                continue
            seen.add(host)
            url = urlsplit(s['url'])
            tls = f'transport http {{\n tls\n tls_server_name {url.hostname}\n}}' if url.scheme == 'https' else ''
            blocks.append(f'''{host} {{
 route {{
  {AUTH}
  reverse_proxy unix//srv/vws-preview-{preview_id(s)}.sock {{
   {STRIP}
   header_up Host {url.netloc}
   header_up Origin {origin(s['url'])}
   {tls}
  }}
 }}
}}''')
    return '\n\n'.join(blocks) + '\n'


def prepare_previews(documents):
    """Bridge the existing container's /srv mount to host-only app listeners."""
    units = Path.home() / '.config/systemd/user'
    wanted = set()
    changed = False
    for doc in documents:
        for s in surfaces(doc['layout']):
            if s['type'] != 'browser' or not local_browser(s):
                continue
            key = preview_id(s)
            unit = 'vws-preview-' + key
            wanted.add(unit + '.socket')
            url = urlsplit(s['url'])
            host = '[::1]' if url.hostname == '::1' else '127.0.0.1'
            port = url.port or (443 if url.scheme == 'https' else 80)
            definitions = {
                '.socket': f'[Socket]\nListenStream=%h/deploy/www/{unit}.sock\nSocketMode=0600\nRemoveOnStop=true\n[Install]\nWantedBy=sockets.target\n',
                '.service': f'[Service]\nExecStart=/usr/lib/systemd/systemd-socket-proxyd {host}:{port}\nNoNewPrivileges=true\n',
            }
            for suffix, content in definitions.items():
                p = units / (unit + suffix)
                if not p.exists() or p.read_text() != content:
                    p.write_text(content)
                    changed = True
    if changed:
        subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    if wanted:
        subprocess.run(['systemctl', '--user', 'enable', '--now', *sorted(wanted)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
