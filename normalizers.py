"""
Módulo de higienização e normalização de dados.
Contém funções puras de validação e formatação utilizadas pelo process_batch.py.
Todas as funções são tolerantes a dados ausentes, nulos ou malformados.
"""

import unicodedata
from datetime import datetime
from typing import Any

# Campeonatos permitidos no filtro de negócio
ALLOWED_CHAMPIONSHIPS = {"SERIE A", "SERIE B"}


def validate_date(value: Any) -> str:
    """
    Valida e normaliza uma data para o formato YYYY-MM-DD.
    Retorna string vazia '' se o valor for nulo, não-string, malformado ou data inexistente.
    Exemplos:
        '1910-09-01'  -> '1910-09-01'
        '2024-02-30'  -> ''  (data inexistente no calendário)
        '01/09/1910'  -> ''  (formato inválido)
        None          -> ''
    """
    if not value or not isinstance(value, str):
        return ""
    cleaned = value.strip()
    try:
        dt = datetime.strptime(cleaned, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return ""


def format_colors(colors_raw: Any) -> str:
    """
    Formata a lista de cores unindo elementos por '|'.
    Suporta listas, tuplas ou string única. Trata nulos e elementos vazios.
    Exemplos:
        ['preto', 'branco'] -> 'preto|branco'
        []                  -> ''
        None                -> ''
    """
    if colors_raw is None:
        return ""
    if isinstance(colors_raw, str):
        colors_raw = [colors_raw]
    if isinstance(colors_raw, (list, tuple)):
        clean_colors = [
            str(c).strip()
            for c in colors_raw
            if c is not None and str(c).strip()
        ]
        return "|".join(clean_colors)
    return ""


def format_nullable_string(value: Any) -> str:
    """
    Trata campos ausentes, nulos (None) ou vazios, retornando string limpa ou ''.
    Exemplos:
        'Timão'    -> 'Timão'
        '  texto ' -> 'texto'
        None       -> ''
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return value.strip()


def format_number_field(value: Any) -> str:
    """
    Trata campos numéricos (idade, gols, número de camisa).
    Converte floats inteiros (ex: 26.0 -> '26') e strings com espaços (' 10 ' -> '10').
    Retorna '' para valores None ou ausentes.
    """
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def normalize_text(text: str) -> str:
    """
    Remove acentos (NFKD Unicode), colapsa espaços extras e converte para caixa alta.
    Exemplo: '  Série  A  ' -> 'SERIE A'
    """
    nfkd = unicodedata.normalize("NFKD", text)
    without_accents = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return " ".join(without_accents.upper().split())


def is_valid_championship(championship_raw: Any) -> bool:
    """
    Verifica se o campeonato pertence à 'SERIE A' ou 'SERIE B',
    tolerando variações de acentuação ('Série A'), maiúsculas/minúsculas e espaços extras.
    Exemplos aceitos: 'SERIE A', 'Série A', 'serie b', '  SÉRIE   B  '
    """
    if not championship_raw or not isinstance(championship_raw, str):
        return False
    return normalize_text(championship_raw) in ALLOWED_CHAMPIONSHIPS
