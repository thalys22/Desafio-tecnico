#!/usr/bin/env python3
"""
Script de processamento em lote de dados de clubes e jogadores de futebol.
Lê um arquivo JSONL linha a linha em streaming (memória O(1)) e gera
dois arquivos CSV: clubs.csv e players.csv.

Utiliza exclusivamente a biblioteca padrão do Python.
As funções de higienização e validação de dados estão em normalizers.py.
"""

import argparse
import csv
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

from normalizers import (
    validate_date,
    format_colors,
    format_nullable_string,
    format_number_field,
    is_valid_championship,
)

# Configuração do Logger
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("process_batch")

# Cabeçalhos dos CSVs conforme o PDF da especificação (ordem e nomes exatos)
CLUB_HEADERS: List[str] = [
    "Id do Clube",
    "Nome",
    "Campeonato",
    "Data de Fundação",
    "Cidade",
    "Estado",
    "País",
    "Estádio",
    "Presidente",
    "Apelido",
    "Cores",
]

PLAYER_HEADERS: List[str] = [
    "Id do Clube",
    "Id do Jogador",
    "Nome",
    "Idade",
    "Gols",
    "Data de Estreia",
    "Posição",
    "Número da Camisa",
]

# Buffer de I/O de 1 MB: reduz syscalls de disco ao processar arquivos de grande porte
IO_BUFFER_SIZE = 1024 * 1024


def process_record(raw_club: Any, line_idx: int) -> Tuple[Optional[Tuple[str, ...]], List[Tuple[str, ...]], Optional[str]]:
    """
    Processa e normaliza um registro de clube (dicionário JSON).

    Retorna: (club_row_tuple, list_of_player_row_tuples, skip_reason)
    - Se o registro for válido, skip_reason é None.
    - Se inválido ou filtrado, club_row é None e skip_reason descreve o motivo.

    Usa tuplas em vez de dicionários para eliminar overhead de alocação e
    lookups de chave por linha — relevante ao processar milhões de registros.
    """
    if not isinstance(raw_club, dict):
        return None, [], "tipo_invalido"

    # 1. club_id é identificador essencial para a chave 1:N com os jogadores
    club_id = format_nullable_string(raw_club.get("club_id"))
    if not club_id:
        return None, [], "club_id_ausente"

    # 2. Filtro de negócio: apenas Série A e Série B
    if not is_valid_championship(raw_club.get("championship")):
        return None, [], "campeonato_filtrado"

    # 3. Tupla do clube na ordem exata das colunas de clubs.csv
    club_row: Tuple[str, ...] = (
        club_id,
        format_nullable_string(raw_club.get("name")),
        format_nullable_string(raw_club.get("championship")),
        validate_date(raw_club.get("founding_date")),
        format_nullable_string(raw_club.get("city")),
        format_nullable_string(raw_club.get("state")),
        format_nullable_string(raw_club.get("country")),
        format_nullable_string(raw_club.get("stadium")),
        format_nullable_string(raw_club.get("president")),
        format_nullable_string(raw_club.get("nickname")),
        format_colors(raw_club.get("colors")),
    )

    # 4. Relação 1:N: processa cada jogador da lista individualmente
    player_rows: List[Tuple[str, ...]] = []
    players_raw = raw_club.get("players")

    if players_raw is not None and not isinstance(players_raw, list):
        logger.warning(
            f"Linha {line_idx} [{club_id}]: Campo 'players' não é uma lista válida "
            f"(tipo: {type(players_raw).__name__}). Nenhum jogador associado."
        )
    elif isinstance(players_raw, list):
        for p_idx, player in enumerate(players_raw, start=1):
            if not isinstance(player, dict):
                logger.warning(f"Linha {line_idx} [{club_id}]: Jogador #{p_idx} ignorado por não ser um objeto JSON.")
                continue

            player_id = format_nullable_string(player.get("player_id"))
            if not player_id:
                logger.warning(f"Linha {line_idx} [{club_id}]: Jogador #{p_idx} ignorado por ausência de 'player_id'.")
                continue

            player_rows.append((
                club_id,
                player_id,
                format_nullable_string(player.get("name")),
                format_number_field(player.get("age")),
                format_number_field(player.get("goals")),
                validate_date(player.get("debut_date")),
                format_nullable_string(player.get("position")),
                format_number_field(player.get("shirt_number")),
            ))

    return club_row, player_rows, None


def process_stream(input_path: str, output_dir: str) -> Tuple[int, int, int, Dict[str, int]]:
    """
    Lê o arquivo JSONL linha a linha em streaming e grava clubs.csv e players.csv.
    Consumo de memória RAM é constante (O(1)), independente do tamanho do arquivo.

    Retorna: (total_linhas, clubes_gerados, jogadores_gerados, contadores_de_descarte)
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Arquivo de entrada não encontrado: '{input_path}'")

    os.makedirs(output_dir, exist_ok=True)

    total_lines = 0
    processed_clubs = 0
    processed_players = 0
    seen_club_ids: Set[str] = set()

    skip_counters: Dict[str, int] = {
        "json_malformado": 0,
        "tipo_invalido": 0,
        "club_id_ausente": 0,
        "club_id_duplicado": 0,
        "campeonato_filtrado": 0,
        "erro_inesperado": 0,
        "linhas_vazias": 0,
    }

    logger.info(f"Iniciando processamento streaming de: {input_path}")
    logger.info(f"Gerando arquivos em: {output_dir}")

    clubs_path = os.path.join(output_dir, "clubs.csv")
    players_path = os.path.join(output_dir, "players.csv")

    with open(input_path, "r", encoding="utf-8", buffering=IO_BUFFER_SIZE) as in_file, \
         open(clubs_path, "w", encoding="utf-8", newline="", buffering=IO_BUFFER_SIZE) as clubs_file, \
         open(players_path, "w", encoding="utf-8", newline="", buffering=IO_BUFFER_SIZE) as players_file:

        clubs_writer = csv.writer(clubs_file, lineterminator="\n")
        players_writer = csv.writer(players_file, lineterminator="\n")

        clubs_writer.writerow(CLUB_HEADERS)
        players_writer.writerow(PLAYER_HEADERS)

        for line_idx, line in enumerate(in_file, start=1):
            total_lines = line_idx
            line_str = line.strip()

            if not line_str:
                skip_counters["linhas_vazias"] += 1
                continue

            # Bloco de isolamento individual: falha em uma linha não aborta as demais
            try:
                raw_club = json.loads(line_str)
                club_row, player_rows, skip_reason = process_record(raw_club, line_idx)

                if skip_reason:
                    skip_counters[skip_reason] += 1
                    if skip_reason == "club_id_ausente":
                        logger.warning(f"Linha {line_idx}: Linha pulada — 'club_id' ausente ou nulo.")
                    elif skip_reason == "tipo_invalido":
                        logger.warning(f"Linha {line_idx}: Linha pulada — conteúdo JSON não é um objeto.")
                    continue

                if club_row:
                    club_id = club_row[0]
                    if club_id in seen_club_ids:
                        skip_counters["club_id_duplicado"] += 1
                        logger.warning(f"Linha {line_idx}: Clube '{club_id}' ignorado — club_id duplicado.")
                        continue

                    seen_club_ids.add(club_id)
                    clubs_writer.writerow(club_row)
                    processed_clubs += 1

                    if player_rows:
                        players_writer.writerows(player_rows)
                        processed_players += len(player_rows)

            except json.JSONDecodeError as err:
                skip_counters["json_malformado"] += 1
                logger.warning(f"Linha {line_idx}: JSON malformado ignorado ({err}).")
            except Exception as err:
                skip_counters["erro_inesperado"] += 1
                logger.warning(f"Linha {line_idx}: Erro inesperado ao processar ({err}).")

    total_skipped = sum(v for k, v in skip_counters.items() if k != "linhas_vazias")

    logger.info("=" * 60)
    logger.info("PROCESSAMENTO CONCLUÍDO COM SUCESSO")
    logger.info(f"Linhas lidas do arquivo:              {total_lines}")
    logger.info(f"Clubes gerados em clubs.csv:          {processed_clubs}")
    logger.info(f"Jogadores gerados em players.csv:     {processed_players}")
    logger.info(f"Total de registros desconsiderados:   {total_skipped}")
    logger.info("Detalhamento de linhas puladas:")
    logger.info(f"  • JSON malformado:                  {skip_counters['json_malformado']}")
    logger.info(f"  • 'club_id' ausente/nulo:            {skip_counters['club_id_ausente']}")
    logger.info(f"  • 'club_id' duplicado:               {skip_counters['club_id_duplicado']}")
    logger.info(f"  • Tipo de registro inválido:         {skip_counters['tipo_invalido']}")
    logger.info(f"  • Campeonato fora da Série A/B:      {skip_counters['campeonato_filtrado']}")
    logger.info(f"  • Erros inesperados:                 {skip_counters['erro_inesperado']}")
    logger.info(f"  • Linhas vazias:                     {skip_counters['linhas_vazias']}")
    logger.info("=" * 60)

    return total_lines, processed_clubs, processed_players, skip_counters


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Processa um arquivo JSONL de clubes/jogadores e gera arquivos CSV em streaming."
    )
    parser.add_argument(
        "input_positional",
        nargs="?",
        default=None,
        help="Caminho do arquivo JSONL de entrada (ex: data/sample_clubes.jsonl)."
    )
    parser.add_argument(
        "-i", "--input",
        dest="input_flag",
        default=None,
        help="Caminho do arquivo JSONL de entrada (alternativa via flag)."
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=".",
        help="Diretório onde clubs.csv e players.csv serão salvos (padrão: diretório atual)."
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_path = args.input_positional or args.input_flag

    if not input_path:
        sample_default = os.path.join("data", "sample_clubes (3) (1) (2) (3).jsonl")
        if os.path.exists(sample_default):
            input_path = sample_default
        else:
            logger.error("Nenhum arquivo de entrada fornecido.")
            logger.info("Uso: python process_batch.py <caminho_do_arquivo.jsonl>")
            logger.info("Ou:   python process_batch.py -i <caminho_do_arquivo.jsonl>")
            sys.exit(1)

    try:
        process_stream(input_path=input_path, output_dir=args.output_dir)
    except Exception as e:
        logger.error(f"Falha fatal na execução do processo: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
