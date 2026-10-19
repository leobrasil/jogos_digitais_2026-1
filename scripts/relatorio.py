#!/usr/bin/env python3
"""
Gera o relatório semanal de commits por aluno a partir de cadastro.json.

Uso:  python3 scripts/relatorio.py --inicio 2026-10-05 --saida relatorio/
Gera na pasta de saída: README.md, grafico_semana.png, grafico_total.png,
dados.csv e alerta.md (texto da issue de alerta).
"""
import argparse
import collections
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
from github_api import NaoEncontrado, get, get_all  # noqa: E402

BRT = timezone(timedelta(hours=-3))
CORES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#6250d6"]


def dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(BRT)


def segunda(d):
    return (d - timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)


def coletar(grupo, inicio):
    """Retorna (commits_unicos, created_at) de todas as branches do repositório."""
    repo = grupo["repo"]
    info, _ = get(f"/repos/{repo}")
    vistos = {}
    try:
        branches = [b["name"] for b in get_all(f"/repos/{repo}/branches")]
    except NaoEncontrado:
        branches = []
    since = inicio.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for br in branches:
        try:
            for c in get_all(f"/repos/{repo}/commits", {"sha": br, "since": since}):
                vistos[c["sha"]] = c
        except NaoEncontrado:
            pass
    return list(vistos.values()), dt(info["created_at"])


def curto(nome):
    p = nome.split()
    return p[0] if len(p) == 1 else f"{p[0]} {p[-1]}"


def grafico(grupos_rot, contagens, titulo, arquivo):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = len(grupos_rot)
    fig, ax = plt.subplots(figsize=(10, 0.55 * n + 1.4))
    maxv = max([sum(v for _, v in c) for c in contagens] + [1])
    ax.set_xlim(0, maxv * 1.6 + 1)
    ax.set_ylim(-0.6, n - 0.4)
    ax.set_yticks(range(n))
    ax.set_yticklabels(list(reversed(grupos_rot)), fontsize=9)
    ax.set_xlabel("Commits")
    ax.set_title(titulo, loc="left", fontsize=12)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", color="#e1e0d9")
    ax.set_axisbelow(True)
    fig.tight_layout()
    rend = fig.canvas.get_renderer()
    inv = ax.transData.inverted()
    for i, (rot, partes) in enumerate(zip(grupos_rot, contagens)):
        y = n - 1 - i
        x = 0
        for j, (aluno, v) in enumerate(partes):
            if v:
                ax.barh(y, v, left=x, color=CORES[j % len(CORES)], height=0.6, edgecolor="white", linewidth=1.5)
                if v / maxv > 0.035:
                    ax.text(x + v / 2, y, str(v), va="center", ha="center", fontsize=8, color="white")
            x += v
        # à direita: total e, em grupos, a contagem de cada aluno com a cor do segmento
        t = ax.text(x + maxv * 0.012, y, f"{x}" if x else "0 commits", va="center", fontsize=9,
                    color="#0b0b0b" if x else "#d03b3b", fontweight="bold")
        if len(partes) > 1:
            for j, (aluno, v) in enumerate(partes):
                x1 = inv.transform(t.get_window_extent(rend))[1][0]
                t = ax.text(x1 + maxv * 0.015, y, f"■ {aluno} {v}", va="center", fontsize=8.5,
                            color="#d03b3b" if v == 0 else CORES[j % len(CORES)])
    fig.savefig(arquivo, dpi=130)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inicio", default=os.environ.get("INICIO", "2026-10-05"))
    ap.add_argument("--cadastro", default=os.path.join(os.path.dirname(__file__), "..", "cadastro.json"))
    ap.add_argument("--saida", default="relatorio")
    args = ap.parse_args()
    os.makedirs(args.saida, exist_ok=True)

    agora = datetime.now(BRT)
    inicio = segunda(datetime.fromisoformat(args.inicio).replace(tzinfo=BRT))
    semanas = []
    s = inicio
    while s <= agora:
        semanas.append(s)
        s += timedelta(days=7)
    fechadas = [w for w in semanas if w + timedelta(days=7) <= agora]
    ultima = len(fechadas) - 1  # índice da última semana fechada (-1 se nenhuma)

    cadastro = json.load(open(args.cadastro, encoding="utf-8"))
    alunos = []          # linhas da tabela
    nao_ident = []       # commits que não batem com nenhum integrante
    suspeitos = []       # commits com data anterior à criação do repositório
    falhas = []          # grupos sem acesso
    graf_rot, graf_sem, graf_tot = [], [], []

    for g in cadastro:
        membros = {m["github"].lower(): m for m in g["integrantes"]}
        cont = {k: [0] * len(semanas) for k in membros}
        try:
            commits, criado = coletar(g, inicio)
        except (NaoEncontrado, Exception) as e:  # noqa: BLE001
            falhas.append((g, str(e)))
            commits, criado = [], None
        extras = collections.Counter()
        for c in commits:
            if len(c.get("parents", [])) > 1:
                continue  # merge automático
            quando = dt(c["commit"]["committer"]["date"])
            i = (quando - inicio).days // 7
            if not 0 <= i < len(semanas):
                continue
            if criado and quando < criado - timedelta(minutes=5):
                suspeitos.append((g, c, quando))
            login_orig = (c.get("author") or {}).get("login") or ""
            login = login_orig.lower()
            if login in cont:
                cont[login][i] += 1
            else:
                quem = login_orig or f"{c['commit']['author']['name']} <{c['commit']['author']['email']}>"
                extras[quem] += 1
        for quem, n in extras.items():
            nao_ident.append((g, quem, n))

        rot = f"{g['repo'].split('/')[0]} ({g['turma']})"
        graf_rot.append(rot)
        graf_sem.append([(curto(membros[k]["nome"]), cont[k][ultima] if ultima >= 0 else 0) for k in membros])
        graf_tot.append([(curto(membros[k]["nome"]), sum(cont[k])) for k in membros])
        for k, m in membros.items():
            alunos.append({"turma": g["turma"], "nome": m["nome"], "github": m["github"], "repo": g["repo"],
                           "semanas": cont[k], "faltas": sum(1 for x in cont[k][:len(fechadas)] if x == 0)})

    # gráficos
    rot_sem = semanas[ultima].strftime("%d/%m") if ultima >= 0 else "-"
    if cadastro:
        grafico(graf_rot, graf_sem, f"Commits por aluno na semana de {rot_sem}",
                os.path.join(args.saida, "grafico_semana.png"))
        grafico(graf_rot, graf_tot, f"Commits por aluno desde {inicio:%d/%m}",
                os.path.join(args.saida, "grafico_total.png"))

    # CSV
    with open(os.path.join(args.saida, "dados.csv"), "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.writer(fp, delimiter=";")
        w.writerow(["Turma", "Aluno", "GitHub", "Repositório",
                    *[f"Sem {x:%d/%m}" for x in semanas], "Total", "Semanas sem commit"])
        for a in sorted(alunos, key=lambda a: (a["turma"], a["nome"])):
            w.writerow([a["turma"], a["nome"], a["github"], a["repo"], *a["semanas"], sum(a["semanas"]), a["faltas"]])

    # README
    zerados = [a for a in alunos if ultima >= 0 and a["semanas"][ultima] == 0]
    L = [f"# Relatório de commits — semana de {rot_sem}",
         "",
         f"Gerado em {agora:%d/%m/%Y %H:%M} · {len(cadastro)} grupos · {len(alunos)} alunos · "
         f"semanas de segunda a domingo, todas as branches, sem contar merges.",
         ""]
    L += [f"## Sem commit na semana de {rot_sem} ({len(zerados)})", ""]
    if zerados:
        for t in sorted({a["turma"] for a in zerados}):
            nomes = ", ".join(f"{a['nome']} (@{a['github']})" for a in zerados if a["turma"] == t)
            L.append(f"- **{t}:** {nomes}")
    else:
        L.append("Todos os alunos fizeram commit. 🎉")
    L += ["", "![Commits na semana](grafico_semana.png)", "", "![Commits no total](grafico_total.png)", ""]
    cab = [f"{x:%d/%m}" + ("*" if x not in fechadas else "") for x in semanas]
    for t in sorted({a["turma"] for a in alunos}):
        L += [f"## Turma {t}", "",
              "| Aluno | GitHub | Repositório | " + " | ".join(cab) + " | Total | Semanas sem commit |",
              "|---|---|---|" + "---:|" * len(cab) + "---:|---:|"]
        for a in sorted([a for a in alunos if a["turma"] == t], key=lambda a: (a["repo"].lower(), a["nome"])):
            cel = []
            for i, v in enumerate(a["semanas"]):
                cel.append(str(v) if v else ("❌" if i < len(fechadas) else "–"))
            L.append(f"| {a['nome']} | @{a['github']} | [{a['repo']}](https://github.com/{a['repo']}) | "
                     + " | ".join(cel) + f" | {sum(a['semanas'])} | {a['faltas']} |")
        L.append("")
    L += ["\\* semana em andamento, ainda não conta como falta.", ""]
    if nao_ident:
        L += ["## Commits não identificados", "",
              "Commits feitos por contas que não estão no cadastro do grupo, ou com e-mail não vinculado "
              "a nenhuma conta do GitHub. Peça ao aluno para adicionar esse e-mail em "
              "*Settings → Emails* do GitHub ou para incluir a conta no cadastro.", "",
              "| Repositório | Autor | Commits |", "|---|---|---:|"]
        L += [f"| {g['repo']} | {q} | {n} |" for g, q, n in nao_ident]
        L.append("")
    if suspeitos:
        L += ["## Commits com data anterior à criação do repositório", "",
              "Possível data retroativa.", "", "| Repositório | Commit | Data |", "|---|---|---|"]
        L += [f"| {g['repo']} | [{c['sha'][:7]}]({c['html_url']}) | {q:%d/%m %H:%M} |" for g, c, q in suspeitos]
        L.append("")
    if falhas:
        L += ["## Repositórios sem acesso", ""]
        L += [f"- {g['repo']} (issue #{g['issue']}): {e}" for g, e in falhas]
        L.append("")
    open(os.path.join(args.saida, "README.md"), "w", encoding="utf-8").write("\n".join(L))

    # texto da issue de alerta
    A = [f"Resumo da semana de {rot_sem}. Relatório completo no README deste repositório.", ""]
    A += [f"**Sem commit ({len(zerados)}):**"] + ([f"- {a['turma']} · {a['nome']} (`{a['github']}`) · {a['repo']}"
                                                  for a in zerados] or ["- ninguém"])
    if nao_ident:
        A += ["", f"**Commits não identificados:** {sum(n for *_, n in nao_ident)}"]
    if falhas:
        A += ["", f"**Repositórios sem acesso:** {', '.join(g['repo'] for g, _ in falhas)}"]
    open(os.path.join(args.saida, "alerta.md"), "w", encoding="utf-8").write("\n".join(A) + "\n")
    print("\n".join(A))


if __name__ == "__main__":
    main()
