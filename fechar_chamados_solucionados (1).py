#!/usr/bin/env python3
"""
Fecha chamados do GLPI que estao "Solucionados" ha mais de N dias.
Usa a API REST do GLPI (apirest.php).

Uso:
    pip install requests
    python fechar_chamados_solucionados.py            # simulacao (nao altera nada)
    python fechar_chamados_solucionados.py --executar # fecha de verdade
"""
import argparse
from datetime import datetime, timedelta

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------- CONFIGURACAO ----------------
GLPI_URL = "https://10.1.100.128/apirest.php/"
APP_TOKEN = "0lH3sbFT6cqWqF0XZQJ2HKESZz1jdxmsW80uqPux"     # Configurar > Geral > API > Cliente da API
USER_TOKEN = "pqTasfv0gsBUsqR5LwES2pQOyz75vopvuOmjxLLR"   # Perfil do usuario > Configuracoes remotas > Token da API
DIAS = 3
VERIFICAR_SSL = False  # certificado do servidor vencido
LOTE = 100             # quantos chamados fechar por requisicao
# ----------------------------------------------

STATUS_SOLUCIONADO = 5
STATUS_FECHADO = 6
CAMPO_ID, CAMPO_STATUS, CAMPO_DATA_SOLUCAO = 2, 12, 17


def iniciar_sessao():
    r = requests.get(f"{GLPI_URL}/initSession", verify=VERIFICAR_SSL,
                     headers={"App-Token": APP_TOKEN,
                              "Authorization": f"user_token {USER_TOKEN}"})
    r.raise_for_status()
    return {"App-Token": APP_TOKEN, "Session-Token": r.json()["session_token"],
            "Content-Type": "application/json"}


def buscar_solucionados(headers):
    """Retorna lista de (id, data_solucao) de todos os chamados com status Solucionado."""
    resultados, inicio, passo = [], 0, 500
    while True:
        params = {
            "criteria[0][field]": CAMPO_STATUS,
            "criteria[0][searchtype]": "equals",
            "criteria[0][value]": STATUS_SOLUCIONADO,
            "forcedisplay[0]": CAMPO_ID,
            "forcedisplay[1]": CAMPO_DATA_SOLUCAO,
            "range": f"{inicio}-{inicio + passo - 1}",
        }
        r = requests.get(f"{GLPI_URL}/search/Ticket", headers=headers,
                         params=params, verify=VERIFICAR_SSL)
        if r.status_code not in (200, 206):
            r.raise_for_status()
        dados = r.json()
        for linha in dados.get("data", []):
            resultados.append((linha[str(CAMPO_ID)], linha.get(str(CAMPO_DATA_SOLUCAO))))
        inicio += passo
        if inicio >= int(dados.get("totalcount", 0)):
            break
    return resultados


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--executar", action="store_true",
                        help="Fecha os chamados de verdade (sem isso, apenas simula)")
    args = parser.parse_args()

    limite = datetime.now() - timedelta(days=DIAS)
    headers = iniciar_sessao()
    try:
        alvos = []
        for ticket_id, data_solucao in buscar_solucionados(headers):
            if not data_solucao:
                continue
            if datetime.strptime(data_solucao, "%Y-%m-%d %H:%M:%S") <= limite:
                alvos.append(ticket_id)
                print(f"Chamado {ticket_id} - solucionado em {data_solucao}")

        print(f"\n{len(alvos)} chamado(s) solucionado(s) ha mais de {DIAS} dias.")
        if not alvos:
            return
        if not args.executar:
            print("Simulacao: nada foi alterado. Rode com --executar para fechar.")
            return

        fechados, falhas = 0, 0
        for n in range(0, len(alvos), LOTE):
            lote = alvos[n:n + LOTE]
            corpo = {"input": [{"id": i, "status": STATUS_FECHADO} for i in lote]}
            r = requests.put(f"{GLPI_URL}/Ticket", headers=headers, json=corpo,
                             verify=VERIFICAR_SSL)
            r.raise_for_status()
            for item in r.json():
                msg = item.get("message", "")
                for tid, ok in item.items():
                    if tid == "message":
                        continue
                    if ok:
                        fechados += 1
                    else:
                        falhas += 1
                        print(f"Chamado {tid}: FALHOU {msg}")
            print(f"Progresso: {min(n + LOTE, len(alvos))}/{len(alvos)}")
        print(f"\nConcluido: {fechados} fechado(s), {falhas} falha(s).")
    finally:
        requests.get(f"{GLPI_URL}/killSession", headers=headers, verify=VERIFICAR_SSL)


if __name__ == "__main__":
    main()
