"""Baixa o COTAHIST diário da B3 e atualiza os arquivos de cotações.

Saídas:
  data/ultimo.csv                 -> último pregão completo (à vista + opções)
  data/historico/AAAA/vista_AAAA-MM.csv -> histórico mensal do mercado à vista
  data/status.json                -> resultado da última execução

Uso:
  python scripts/atualizar.py                # processa pregões pendentes (até 10 dias)
  python scripts/atualizar.py --ano 2025     # carga histórica anual (só à vista)
"""
import argparse
import csv
import datetime as dt
import io
import json
import os
import sys
import zipfile
from zoneinfo import ZoneInfo

import requests

BASE = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/"
UA = {"User-Agent": "Mozilla/5.0 (cotacoes-b3 GitHub Action)"}
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(RAIZ, "data")
HIST = os.path.join(DATA, "historico")
STATUS = os.path.join(DATA, "status.json")

MERCADOS = {"010": "vista", "070": "call", "080": "put"}
CAMPOS = ["data", "ticker", "mercado", "especificacao", "abertura", "maxima",
          "minima", "media", "fechamento", "negocios", "quantidade", "volume",
          "strike", "vencimento", "isin"]


def preco(s):
    return f"{int(s) / 100:.2f}"


def parse_linha(l):
    if l[0:2] != "01":
        return None
    tpmerc = l[24:27]
    if tpmerc not in MERCADOS:
        return None
    codbdi = l[10:12]
    # à vista: só lote padrão (02), FIIs (12), ETFs (14), BDRs (fora do 96 fracionário)
    if tpmerc == "010" and codbdi == "96":
        return None
    d = l[2:10]
    venc = l[202:210].strip()
    return {
        "data": f"{d[0:4]}-{d[4:6]}-{d[6:8]}",
        "ticker": l[12:24].strip(),
        "mercado": MERCADOS[tpmerc],
        "especificacao": l[39:49].strip(),
        "abertura": preco(l[56:69]),
        "maxima": preco(l[69:82]),
        "minima": preco(l[82:95]),
        "media": preco(l[95:108]),
        "fechamento": preco(l[108:121]),
        "negocios": int(l[147:152]),
        "quantidade": int(l[152:170]),
        "volume": preco(l[170:188]),
        "strike": preco(l[188:201]) if tpmerc != "010" else "",
        "vencimento": (f"{venc[0:4]}-{venc[4:6]}-{venc[6:8]}"
                       if tpmerc != "010" and venc not in ("", "99991231") else ""),
        "isin": l[230:242].strip(),
    }


def baixar(nome, so_vista=False):
    r = requests.get(BASE + nome, headers=UA, timeout=600)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    if r.content[:2] != b"PK":  # B3 devolve HTML quando o arquivo não existe
        return None
    z = zipfile.ZipFile(io.BytesIO(r.content))
    out = []
    with z.open(z.namelist()[0]) as f:
        for raw in io.TextIOWrapper(f, encoding="latin-1"):
            if so_vista and raw[24:27] != "010":
                continue
            x = parse_linha(raw)
            if x:
                out.append(x)
    return out


def gravar_hist(linhas):
    """Histórico à vista em arquivos mensais: data/historico/AAAA/vista_AAAA-MM.csv"""
    por_mes = {}
    for l in linhas:
        if l["mercado"] == "vista":
            por_mes.setdefault(l["data"][:7], []).append(l)
    for mes, novas in por_mes.items():
        pasta = os.path.join(HIST, mes[:4])
        os.makedirs(pasta, exist_ok=True)
        caminho = os.path.join(pasta, f"vista_{mes}.csv")
        existentes = []
        if os.path.exists(caminho):
            with open(caminho, newline="", encoding="utf-8") as f:
                existentes = list(csv.DictReader(f))
        datas_novas = {l["data"] for l in novas}
        todas = [e for e in existentes if e["data"] not in datas_novas] + novas
        todas.sort(key=lambda x: (x["data"], x["ticker"]))
        with open(caminho, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CAMPOS)
            w.writeheader()
            w.writerows(todas)


def gravar_ultimo(linhas):
    # opções só entram se tiveram negócio no dia
    linhas = [l for l in linhas if l["mercado"] == "vista" or l["negocios"] > 0]
    linhas = sorted(linhas, key=lambda x: (x["mercado"], x["ticker"]))
    with open(os.path.join(DATA, "ultimo.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(linhas)


def ler_status():
    if os.path.exists(STATUS):
        with open(STATUS, encoding="utf-8") as f:
            return json.load(f)
    return {}


def salvar_status(st):
    with open(STATUS, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)


def diario():
    st = ler_status()
    hoje = dt.datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    ultimo = st.get("ultimo_pregao")
    inicio = (dt.date.fromisoformat(ultimo) + dt.timedelta(days=1)) if ultimo else hoje - dt.timedelta(days=10)
    inicio = max(inicio, hoje - dt.timedelta(days=10))
    processados, erros = [], []
    d = inicio
    while d <= hoje:
        if d.weekday() < 5:
            try:
                linhas = baixar(f"COTAHIST_D{d:%d%m%Y}.ZIP")
                if linhas:
                    gravar_hist(linhas)
                    gravar_ultimo(linhas)
                    st["ultimo_pregao"] = d.isoformat()
                    st["linhas_ultimo"] = len(linhas)
                    processados.append(d.isoformat())
            except Exception as e:  # noqa: BLE001
                erros.append(f"{d}: {e}")
        d += dt.timedelta(days=1)
    st["execucao"] = dt.datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds")
    st["processados_nesta_execucao"] = processados
    st["erros"] = erros
    salvar_status(st)
    print(json.dumps(st, ensure_ascii=False, indent=2))


def anual(ano):
    linhas = baixar(f"COTAHIST_A{ano}.ZIP", so_vista=True)
    if not linhas:
        sys.exit(f"Arquivo anual {ano} não encontrado")
    gravar_hist(linhas)
    st = ler_status()
    st.setdefault("anos_carregados", [])
    if ano not in st["anos_carregados"]:
        st["anos_carregados"].append(ano)
        st["anos_carregados"].sort()
    salvar_status(st)
    print(f"{ano}: {sum(1 for l in linhas if l['mercado'] == 'vista')} linhas à vista")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--ano", type=int)
    p.add_argument("--pendentes", action="store_true",
                   help="processa os anos listados em carga_pendente.txt e apaga o arquivo")
    a = p.parse_args()
    os.makedirs(DATA, exist_ok=True)
    if a.pendentes:
        arq = os.path.join(RAIZ, "carga_pendente.txt")
        if os.path.exists(arq):
            anos = [int(x) for x in open(arq).read().split() if x.strip()]
            for ano in anos:
                anual(ano)
            os.remove(arq)
    elif a.ano:
        anual(a.ano)
    else:
        diario()
