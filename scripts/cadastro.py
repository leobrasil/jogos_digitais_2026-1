#!/usr/bin/env python3
"""
Valida uma issue de cadastro e atualiza cadastro.json.

Variáveis de ambiente (preenchidas pela Action):
  ISSUE_BODY, ISSUE_NUMBER, ISSUE_AUTHOR, PROFESSOR, COMMITS_TOKEN
Saídas:
  resultado.md        texto do comentário que será postado na issue
  GITHUB_OUTPUT       status=ok|erro
"""
import json
import os
import re
import sys
import urllib.error
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))
from github_api import NaoEncontrado, get, get_all, parse_repo, request  # noqa: E402

TURMAS = ["4J11", "4J12", "4H11", "4H12"]
ARQ = os.path.join(os.path.dirname(__file__), "..", "cadastro.json")
BRT = timezone(timedelta(hours=-3))


def campos(body):
    """Lê as seções '### Título' que o GitHub gera a partir do Issue Form."""
    out = {}
    for bloco in re.split(r"^### ", body.replace("\r\n", "\n"), flags=re.M)[1:]:
        titulo, _, valor = bloco.partition("\n")
        valor = valor.strip()
        out[titulo.strip()] = "" if valor == "_No response_" else valor
    return out


def ler_integrantes(texto):
    itens, erros = [], []
    for n, linha in enumerate(texto.splitlines(), 1):
        linha = linha.strip().strip("`").lstrip("-*").strip()
        if not linha:
            continue
        partes = re.split(r"\s*[;,\t|]\s*", linha)
        if len(partes) < 2:
            erros.append(f"Linha {n} (`{linha}`): use o formato `Nome completo; usuário do GitHub`.")
            continue
        nome, usuario = partes[0].strip(), partes[-1].strip()
        usuario = usuario.rstrip("/").split("/")[-1].lstrip("@")
        if not nome or not usuario:
            erros.append(f"Linha {n} (`{linha}`): falta o nome ou o usuário.")
            continue
        itens.append({"nome": nome, "github": usuario})
    return itens, erros


def acessar(owner, nome):
    try:
        return get(f"/repos/{owner}/{nome}")[0]
    except (NaoEncontrado, urllib.error.HTTPError):
        return None


def aceitar_convite(full_name):
    """Aceita automaticamente o convite de colaborador do repositório informado."""
    try:
        for conv in get_all("/user/repository_invitations"):
            if conv["repository"]["full_name"].lower() == full_name.lower():
                request("PATCH", f"/user/repository_invitations/{conv['id']}")
                return True
    except Exception as e:  # sem permissão para convites: segue sem aceitar
        print(f"aviso: não foi possível verificar convites ({e})", file=sys.stderr)
    return False


def main():
    body = os.environ.get("ISSUE_BODY", "")
    issue = int(os.environ.get("ISSUE_NUMBER", "0"))
    autor = os.environ.get("ISSUE_AUTHOR", "")
    prof = os.environ.get("PROFESSOR", "leobrasil")

    f = campos(body)
    erros, avisos = [], []

    turma = f.get("Turma", "").strip()
    if turma not in TURMAS:
        erros.append(f"Turma inválida: `{turma or 'vazia'}`. Escolha uma de: {', '.join(TURMAS)}.")

    repo_full, privado = None, False
    alvo = parse_repo(f.get("Repositório do projeto", ""))
    if not alvo:
        erros.append("Não entendi o link do repositório. Use o formato `https://github.com/usuario/repositorio`.")
    else:
        owner, nome = alvo
        info = acessar(owner, nome)
        if info is None and aceitar_convite(f"{owner}/{nome}"):
            info = acessar(owner, nome)
        if info is None:
            erros.append(
                f"Não consegui acessar `{owner}/{nome}`. Confira se o link está certo. "
                f"Se o repositório for **privado**, adicione `{prof}` como colaborador "
                "(*Settings → Collaborators → Add people*) e depois **edite esta issue** "
                "(qualquer alteração serve) para eu verificar de novo.")
        else:
            repo_full, privado = info["full_name"], info["private"]
            aceitar_convite(repo_full)

    integrantes, e_int = ler_integrantes(f.get("Integrantes", ""))
    erros += e_int
    if not integrantes and not e_int:
        erros.append("Informe pelo menos um integrante.")
    validos = []
    for it in integrantes:
        try:
            u, _ = get(f"/users/{it['github']}")
            validos.append({"nome": it["nome"], "github": u["login"]})
        except NaoEncontrado:
            erros.append(f"O usuário do GitHub `{it['github']}` ({it['nome']}) não existe.")
    logins = [v["github"].lower() for v in validos]
    if len(set(logins)) != len(logins):
        erros.append("Há usuários do GitHub repetidos na lista de integrantes.")
    if autor and logins and autor.lower() not in logins:
        avisos.append(f"Quem abriu a issue (`{autor}`) não está na lista de integrantes. Confira se esqueceu alguém.")

    cadastro = json.load(open(ARQ, encoding="utf-8")) if os.path.exists(ARQ) else []
    outros = [g for g in cadastro if g["issue"] != issue]
    if repo_full:
        for g in outros:
            if g["repo"].lower() == repo_full.lower():
                erros.append(f"O repositório `{repo_full}` já foi cadastrado na issue #{g['issue']}. "
                             "Para alterar, edite aquela issue.")
    for g in outros:
        for m in g["integrantes"]:
            if m["github"].lower() in logins:
                erros.append(f"`{m['github']}` já está no grupo do repositório `{g['repo']}` (issue #{g['issue']}).")

    status = "erro" if erros else "ok"
    if status == "ok":
        reg = {"repo": repo_full, "turma": turma, "jogo": f.get("Nome do jogo", ""),
               "issue": issue, "privado": privado, "integrantes": validos,
               "atualizado": datetime.now(BRT).strftime("%Y-%m-%d %H:%M")}
        cadastro = sorted(outros + [reg], key=lambda g: (g["turma"], g["repo"].lower()))
        with open(ARQ, "w", encoding="utf-8") as fp:
            json.dump(cadastro, fp, ensure_ascii=False, indent=2)
            fp.write("\n")
        linhas = [f"| {m['nome']} | @{m['github']} |" for m in validos]
        msg = (f"### ✅ Cadastro confirmado\n\n**Turma:** {turma}  \n**Repositório:** "
               f"[{repo_full}](https://github.com/{repo_full})\n\n| Integrante | GitHub |\n|---|---|\n"
               + "\n".join(linhas)
               + "\n\nA partir de agora os commits de cada integrante serão contados toda semana "
                 "(segunda a domingo), em todas as branches. Lembre-se de fazer commits com a **sua própria conta**.")
    else:
        msg = ("### ❌ Cadastro não concluído\n\nCorrija os itens abaixo **editando esta issue** "
               "(no menu `···` da primeira mensagem → *Edit*). A verificação roda de novo automaticamente.\n\n"
               + "\n".join(f"- {e}" for e in erros))
    if avisos:
        msg += "\n\n**Atenção:**\n" + "\n".join(f"- {a}" for a in avisos)

    open("resultado.md", "w", encoding="utf-8").write(msg + "\n")
    if os.environ.get("GITHUB_OUTPUT"):
        open(os.environ["GITHUB_OUTPUT"], "a").write(f"status={status}\n")
    print(msg)


if __name__ == "__main__":
    main()
