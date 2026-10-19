"""Acesso mínimo à API REST do GitHub, só com a biblioteca padrão."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"


class NaoEncontrado(Exception):
    pass


def _token():
    return os.environ.get("COMMITS_TOKEN") or os.environ.get("GITHUB_TOKEN", "")


def get(path, params=None):
    url = path if path.startswith("http") else API + path
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if _token():
        headers["Authorization"] = f"Bearer {_token()}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r), r.headers.get("Link", "")
    except urllib.error.HTTPError as e:
        if e.code in (404, 409):  # 409 = repositório vazio
            raise NaoEncontrado(f"{e.code}") from e
        raise


def request(method, path, body=None):
    url = API + path
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
               "Authorization": f"Bearer {_token()}"}
    data = json.dumps(body).encode() if body is not None else None
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        txt = r.read()
        return json.loads(txt) if txt else None


def get_all(path, params=None):
    """Percorre todas as páginas de uma listagem."""
    params = dict(params or {}, per_page=100)
    data, link = get(path, params)
    yield from data
    while 'rel="next"' in link:
        nxt = [p.split(";")[0].strip(" <>") for p in link.split(",") if 'rel="next"' in p][0]
        data, link = get(nxt)
        yield from data


def parse_repo(texto):
    """Aceita https://github.com/dono/repo(.git), github.com/dono/repo ou dono/repo."""
    t = texto.strip().strip("<>").rstrip("/")
    if t.endswith(".git"):
        t = t[:-4]
    for pref in ("https://", "http://"):
        if t.startswith(pref):
            t = t[len(pref):]
    if t.startswith("www."):
        t = t[4:]
    if t.startswith("github.com/"):
        t = t[len("github.com/"):]
    partes = t.split("/")
    if len(partes) < 2 or not partes[0] or not partes[1]:
        return None
    return partes[0], partes[1]
