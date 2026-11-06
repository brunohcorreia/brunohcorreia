#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera um README de perfil estilo neofetch/fastfetch (tema Gruvbox) e ATUALIZA
sozinho os números do GitHub (repos, stars, commits, seguidores, linhas de
código) via GitHub Actions.

COMO RODA
  - No GitHub Actions (automático): o workflow em .github/workflows/profile.yml
    roda este script todo dia, passando o token e o usuário por variáveis de
    ambiente, e faz commit dos SVGs atualizados.
  - Localmente (pra testar o visual):  python today.py
    Sem token ele usa números 0 (placeholder), mas o layout/tema aparece igual.

VARIÁVEIS DE AMBIENTE (lidas automaticamente no Actions)
  ACCESS_TOKEN : Personal Access Token (classic) com escopos  repo  e  read:user
  USER_NAME    : seu usuário do GitHub (ex.: brunohcorreia)

Dependência:  requests   (instalada pelo workflow)
"""

import os
import json
import sys
import hashlib

# ===========================================================================
#  👇  SUAS INFORMAÇÕES — edite à vontade  👇
#  (os números do GitHub são preenchidos sozinhos; aqui é só o texto fixo)
# ===========================================================================
CONFIG = {
    "title": "bruno@arch",
    "sections": [
        {"header": None, "rows": [
            ("OS",     "Arch, CachyOS, Windows, Ubuntu"),
            ("Uptime", "24 anos"),
            ("Host",   "Data & Research Analyst"),
            ("Org",    "More in Common Brasil"),
            ("Edu",    "BSc Sistemas de Informação, USP"),
        ]},
        {"header": "Skills", "rows": [
            ("Languages", "Python, Rust, SQL"),
            ("Data",      "pandas, PostgreSQL, SQLite"),
            ("Tools",     "Docker, Git, Google Cloud"),
        ]},
        {"header": "Contact", "rows": [
            ("Email",  "bruno@moreincommon.org.br"),
            ("GitHub", "brunohcorreia"),
        ]},
    ],
    # Arte da esquerda: lida deste arquivo (sua foto em ASCII).
    # Pra trocar a arte, é só editar/substituir o ascii_art.txt.
    "ascii_file": "ascii_art.txt",
}


def get_ascii():
    """Lê a arte ASCII do arquivo; se não achar, usa um octocat simples."""
    try:
        with open(CONFIG["ascii_file"], encoding="utf-8") as f:
            lines = f.read().split("\n")
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        if lines:
            return lines
    except Exception:
        pass
    return ["   .mmm.", " .mMMMMMm.", " mMM MMM MMm", "  mMMMMMMMm", "    mMMMm"]
# ===========================================================================
#  👆  PARE AQUI (abaixo é o motor)  👆
# ===========================================================================

N = 60   # largura do painel direito em caracteres

# ---- Paleta Gruvbox (dark + light) ----
THEMES = {
    "dark": {
        "bg": "#282828", "bar": "#1d2021", "border": "#3c3836",
        "text": "#ebdbb2", "label": "#fabd2f", "value": "#83a598",
        "leader": "#504945", "dash": "#665c54",
        "green": "#b8bb26", "red": "#fb4934", "ascii": "#ebdbb2",
        "c_min": "#fabd2f", "c_max": "#b8bb26", "c_close": "#fb4934",
    },
    "light": {
        "bg": "#fbf1c7", "bar": "#ebdbb2", "border": "#d5c4a1",
        "text": "#3c3836", "label": "#b57614", "value": "#076678",
        "leader": "#d5c4a1", "dash": "#a89984",
        "green": "#79740e", "red": "#9d0006", "ascii": "#3c3836",
        "c_min": "#b57614", "c_max": "#79740e", "c_close": "#9d0006",
    },
}

FONT = "'JetBrains Mono','Cascadia Code','Fira Code',Consolas,'Courier New',monospace"
FS = 14.5
LH = 20
CW = FS * 0.60

# ---------------------------------------------------------------------------
#  Coleta de estatísticas do GitHub (GraphQL)
# ---------------------------------------------------------------------------
API = "https://api.github.com/graphql"
CACHE_FILE = "cache/stats_cache.json"


def gql(token, query, variables):
    import requests
    r = requests.post(API, json={"query": query, "variables": variables},
                      headers={"Authorization": f"Bearer {token}"}, timeout=60)
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def load_cache():
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(cache):
    os.makedirs("cache", exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=1)


def fetch_stats(token, login):
    """Retorna dict com repos, contributed, stars, commits, followers, add, del."""
    # 1) dados básicos do usuário
    q_user = """
    query($login:String!){
      user(login:$login){
        id
        followers { totalCount }
        repositoriesContributedTo(contributionTypes:[COMMIT,PULL_REQUEST,REPOSITORY]) { totalCount }
        repositories(ownerAffiliations:OWNER) { totalCount }
      }
    }"""
    u = gql(token, q_user, {"login": login})["user"]
    owner_id = u["id"]
    followers = u["followers"]["totalCount"]
    contributed = u["repositoriesContributedTo"]["totalCount"]
    repos = u["repositories"]["totalCount"]

    # 2) percorre os repositórios (donos) para stars + histórico
    q_repos = """
    query($login:String!, $after:String){
      user(login:$login){
        repositories(first:100, after:$after, ownerAffiliations:OWNER,
                     orderBy:{field:CREATED_AT, direction:ASC}){
          pageInfo { hasNextPage endCursor }
          nodes {
            nameWithOwner
            stargazerCount
            defaultBranchRef {
              target { ... on Commit { history(first:1){ totalCount } } }
            }
          }
        }
      }
    }"""
    repo_list, after = [], None
    while True:
        page = gql(token, q_repos, {"login": login, "after": after})
        conn = page["user"]["repositories"]
        repo_list.extend(conn["nodes"])
        if conn["pageInfo"]["hasNextPage"]:
            after = conn["pageInfo"]["endCursor"]
        else:
            break

    stars = sum(r["stargazerCount"] for r in repo_list)

    # 3) linhas de código + commits do usuário em cada repo (com cache)
    #    A chave do cache é um HASH SHA-256 do nome do repo. Assim o arquivo
    #    em cache/ (que é commitado no repo público) NUNCA expõe os nomes dos
    #    seus repositórios — inclusive os privados. O cache é reconstruído do
    #    zero a cada rodada, então nenhum nome antigo sobra no arquivo.
    old_cache = load_cache()
    new_cache = {}
    total_commits = total_add = total_del = 0
    for r in repo_list:
        name = r["nameWithOwner"]
        branch = r.get("defaultBranchRef")
        if not branch or not branch.get("target"):
            continue
        key = hashlib.sha256(name.encode("utf-8")).hexdigest()
        n_commits = branch["target"]["history"]["totalCount"]  # commits no branch
        cached = old_cache.get(key)
        if cached and cached.get("branch_commits") == n_commits:
            c, a, d = cached["commits"], cached["additions"], cached["deletions"]
        else:
            # recontar esse repo (novo ou mudou desde o último cache)
            c, a, d = count_repo(token, owner_id, name)
        new_cache[key] = {"branch_commits": n_commits,
                          "commits": c, "additions": a, "deletions": d}
        total_commits += c
        total_add += a
        total_del += d
    save_cache(new_cache)

    return {
        "repos": repos, "contributed": contributed, "stars": stars,
        "commits": total_commits, "followers": followers,
        "loc": total_add - total_del, "add": total_add, "del": total_del,
    }


def count_repo(token, owner_id, name_with_owner):
    """Soma commits/adições/remoções feitos pelo usuário no branch padrão."""
    owner, name = name_with_owner.split("/", 1)
    q = """
    query($owner:String!, $name:String!, $id:ID!, $after:String){
      repository(owner:$owner, name:$name){
        defaultBranchRef { target { ... on Commit {
          history(first:100, after:$after, author:{id:$id}){
            totalCount
            pageInfo { hasNextPage endCursor }
            nodes { additions deletions }
          }
        }}}
      }
    }"""
    commits = add = dele = 0
    after = None
    first = True
    while True:
        d = gql(token, q, {"owner": owner, "name": name, "id": owner_id, "after": after})
        ref = d["repository"]["defaultBranchRef"]
        if not ref or not ref["target"]:
            break
        hist = ref["target"]["history"]
        if first:
            commits = hist["totalCount"]
            first = False
        for node in hist["nodes"]:
            add += node["additions"]
            dele += node["deletions"]
        if hist["pageInfo"]["hasNextPage"]:
            after = hist["pageInfo"]["endCursor"]
        else:
            break
    return commits, add, dele


def fmt(n):
    return f"{n:,}"


# ---------------------------------------------------------------------------
#  Renderização do SVG
# ---------------------------------------------------------------------------
def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;"))


def tspan(text, color, c):
    return f'<tspan fill="{c[color]}">{esc(text)}</tspan>'


def row_segments(label, value):
    if isinstance(value, str):
        value = [(value, "value")]
    vlen = sum(len(t) for t, _ in value)
    left = f"{label}: "
    dots = max(N - 2 - len(left) - 1 - 1 - vlen, 1)
    segs = [(".", "label"), (" ", "text"), (left, "label"),
            (" ", "text"), ("." * dots, "leader"), (" ", "text")]
    return segs + value


def header_segments(name):
    dashes = max(N - 2 - len(name) - 1, 2)
    return [("- ", "dash"), (name + " ", "label"), ("-" * dashes, "dash")]


def title_segments(title):
    dashes = max(N - len(title) - 1, 2)
    return [(title + " ", "label"), ("-" * dashes, "dash")]


def stats_section(s):
    return {"header": "GitHub Stats", "rows": [
        ("Repos", [(fmt(s["repos"]), "value"), (" {Contributed: ", "text"),
                   (fmt(s["contributed"]), "value"), ("} | ", "text"),
                   ("Stars: ", "label"), (fmt(s["stars"]), "value")]),
        ("Commits", [(fmt(s["commits"]), "value"), (" | ", "text"),
                     ("Followers: ", "label"), (fmt(s["followers"]), "value")]),
        ("Lines of Code", [(f'+{fmt(s["add"])}', "green"), ("  /  ", "text"),
                           (f'-{fmt(s["del"])}', "red")]),
    ]}


def render(theme, stats):
    c = THEMES[theme]
    sections = CONFIG["sections"] + [stats_section(stats)]

    lines = [title_segments(CONFIG["title"]), None]
    for sec in sections:
        if sec["header"]:
            lines.append(header_segments(sec["header"]))
        for label, value in sec["rows"]:
            lines.append(row_segments(label, value))
        lines.append(None)
    if lines and lines[-1] is None:
        lines.pop()

    art = get_ascii()
    n_ascii = max(len(art), 1)
    pad_top, pad_bottom = 58, 24
    info_h = len(lines) * LH
    H = int(pad_top + info_h + pad_bottom)
    # a arte é escalada pra ter ~a mesma altura do painel de infos:
    # quanto mais densa (mais linhas), menor a fonte -> parece foto e não cresce o card
    ascii_fs = max(6.0, min(13.0, info_h / (n_ascii * 1.10)))
    alh = ascii_fs * 1.10
    ascii_cw = ascii_fs * 0.60
    art_w = max((len(l) for l in art), default=20)
    ix = int(28 + art_w * ascii_cw + 30)
    W = int(ix + N * CW + 40)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
           f'viewBox="0 0 {W} {H}" font-family="{FONT}">']
    out.append(f'<rect x="4" y="4" width="{W-8}" height="{H-8}" rx="10" '
               f'fill="{c["bg"]}" stroke="{c["border"]}" stroke-width="1.5"/>')
    out.append(f'<rect x="4" y="4" width="{W-8}" height="34" rx="10" fill="{c["bar"]}"/>')
    out.append(f'<rect x="4" y="20" width="{W-8}" height="18" fill="{c["bar"]}"/>')
    # título à esquerda no bar
    out.append(f'<text x="18" y="27" font-size="13" fill="{c["dash"]}">'
               f'{esc(CONFIG["title"])}: ~</text>')
    # controles de janela estilo chevron (GNOME/KDE: "< >" rotacionados) + fechar
    cy = 21
    x3 = W - 22; x2 = x3 - 24; x1 = x2 - 24
    sw = 1.7
    # minimizar  =  chevron pra baixo  (∨)
    out.append(f'<polyline points="{x1-5},{cy-2} {x1},{cy+3} {x1+5},{cy-2}" '
               f'fill="none" stroke="{c["c_min"]}" stroke-width="{sw}" '
               f'stroke-linecap="round" stroke-linejoin="round"/>')
    # maximizar  =  chevron pra cima  (∧)
    out.append(f'<polyline points="{x2-5},{cy+3} {x2},{cy-2} {x2+5},{cy+3}" '
               f'fill="none" stroke="{c["c_max"]}" stroke-width="{sw}" '
               f'stroke-linecap="round" stroke-linejoin="round"/>')
    # fechar  =  X
    out.append(f'<line x1="{x3-5}" y1="{cy-5}" x2="{x3+5}" y2="{cy+5}" '
               f'stroke="{c["c_close"]}" stroke-width="{sw}" stroke-linecap="round"/>')
    out.append(f'<line x1="{x3+5}" y1="{cy-5}" x2="{x3-5}" y2="{cy+5}" '
               f'stroke="{c["c_close"]}" stroke-width="{sw}" stroke-linecap="round"/>')

    art_h = n_ascii * alh
    ay0 = pad_top + max(0, (info_h - art_h) / 2) + ascii_fs
    out.append(f'<g fill="{c["ascii"]}" font-size="{ascii_fs:.2f}" xml:space="preserve">')
    for i, line in enumerate(art):
        out.append(f'<text x="28" y="{ay0 + i*alh:.2f}">{esc(line)}</text>')
    out.append('</g>')

    y0 = pad_top + 14
    out.append(f'<g font-size="{FS}" xml:space="preserve">')
    for i, segs in enumerate(lines):
        if segs is None:
            continue
        inner = "".join(tspan(t, col, c) for t, col in segs)
        out.append(f'<text x="{ix}" y="{y0 + i*LH}">{inner}</text>')
    out.append('</g>')
    out.append('</svg>')
    return "\n".join(out)


# ---------------------------------------------------------------------------
#  Main
# ---------------------------------------------------------------------------
def main():
    token = os.environ.get("ACCESS_TOKEN")
    login = os.environ.get("USER_NAME", "brunohcorreia")

    if token:
        print(f"Buscando estatísticas de @{login}...")
        try:
            stats = fetch_stats(token, login)
            print("OK:", stats)
        except Exception as e:
            print("Falha ao buscar stats:", e, file=sys.stderr)
            stats = placeholder()
    else:
        print("Sem ACCESS_TOKEN — usando números 0 (só prévia de layout).")
        stats = placeholder()

    for theme in ("dark", "light"):
        fname = f"{theme}_mode.svg"
        with open(fname, "w", encoding="utf-8") as f:
            f.write(render(theme, stats))
        print("gerado:", fname)


def placeholder():
    return {"repos": 0, "contributed": 0, "stars": 0, "commits": 0,
            "followers": 0, "loc": 0, "add": 0, "del": 0}


if __name__ == "__main__":
    main()
