import os
import csv
import json
import tempfile
import unittest

from process_batch import process_stream

class TestStreamingProcessing(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.input_file = os.path.join(self.temp_dir.name, "test_input.jsonl")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_resilience_and_filtering(self):
        lines = [
            # 1. Clube Válido (Série A) com jogador válido
            json.dumps({
                "club_id": "FLA",
                "name": "Flamengo, Regatas",
                "championship": "SERIE A",
                "founding_date": "1895-11-17",
                "city": "Rio de Janeiro",
                "state": "RJ",
                "country": "Brasil",
                "stadium": "Maracanã",
                "president": "Rodolfo Landim",
                "nickname": "Mengão",
                "colors": ["vermelho", "preto"],
                "players": [
                    {
                        "player_id": "FLA-14",
                        "name": "Arrascaeta",
                        "age": 30.0, # Float 30.0 -> deve ser formatado como "30"
                        "goals": 12,
                        "debut_date": "2019-01-12",
                        "position": "Meia",
                        "shirt_number": " 14 " # String com espaço -> "14"
                    }
                ]
            }),
            # 2. Linha com JSON Corrompido (JSONDecodeError)
            "{ club_id: 'CORRUPTED', name: invalid json syntax ",
            # 3. Clube sem club_id (Deve ser ignorado)
            json.dumps({
                "name": "Clube Sem ID",
                "championship": "SERIE A"
            }),
            # 4. Clube com 'players' não sendo lista (ex: string ou número) -> Clube mantido, 0 jogadores
            json.dumps({
                "club_id": "VAS",
                "name": "Vasco da Gama",
                "championship": "SERIE A",
                "founding_date": "1898-08-21",
                "players": "tipo_invalido_nao_lista"
            }),
            # 5. Clube sem campeonato válido (Deve ser ignorado)
            json.dumps({
                "club_id": "BOT-RJ",
                "name": "Botafogo",
                "championship": "SERIE C",
                "players": []
            }),
            # 6. Clube com club_id DUPLICADO (já existe "FLA" na linha 1 -> deve ser ignorado)
            json.dumps({
                "club_id": "FLA",
                "name": "Clube Flamengo Duplicado",
                "championship": "SERIE A",
                "players": []
            }),
            # 7. Clube válido contendo 1 jogador válido e 1 jogador corrompido (sem player_id)
            json.dumps({
                "club_id": "FLU",
                "name": "Fluminense",
                "championship": "Série A",
                "founding_date": "1902-07-32", # Data inexistente -> deve virar ""
                "players": [
                    {
                        "player_id": "FLU-10",
                        "name": "Ganso",
                        "age": 34,
                        "goals": 5,
                        "debut_date": "invalid-date",
                        "position": "Meia",
                        "shirt_number": 10
                    },
                    {
                        # Jogador sem player_id -> deve ser ignorado sem derrubar Ganso nem Fluminense
                        "name": "Jogador Sem ID",
                        "age": 20
                    }
                ]
            })
        ]

        with open(self.input_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        # Processa o streaming
        total, clubs, players, skip_counters = process_stream(self.input_file, self.temp_dir.name)

        # Asserções de resiliência e contagem
        self.assertEqual(total, 7)
        self.assertEqual(clubs, 3)     # FLA, VAS, FLU
        self.assertEqual(players, 2)   # Arrascaeta (FLA-14) e Ganso (FLU-10)
        
        # Detalhamento de linhas desconsideradas
        self.assertEqual(skip_counters["json_malformado"], 1)
        self.assertEqual(skip_counters["club_id_ausente"], 1)
        self.assertEqual(skip_counters["club_id_duplicado"], 1)
        self.assertEqual(skip_counters["campeonato_filtrado"], 1)
        self.assertEqual(skip_counters["tipo_invalido"], 0)

        # Verificação do arquivo clubs.csv gerado
        clubs_csv = os.path.join(self.temp_dir.name, "clubs.csv")
        with open(clubs_csv, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            self.assertEqual(len(reader), 3)
            self.assertEqual(reader[0]["Id do Clube"], "FLA")
            self.assertEqual(reader[1]["Id do Clube"], "VAS") # VAS mantido mesmo com players inválido
            self.assertEqual(reader[2]["Id do Clube"], "FLU")

        # Verificação do arquivo players.csv gerado (Valida format_number_field de float 30.0 -> "30" e " 14 " -> "14")
        players_csv = os.path.join(self.temp_dir.name, "players.csv")
        with open(players_csv, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            self.assertEqual(len(reader), 2)
            self.assertEqual(reader[0]["Id do Jogador"], "FLA-14")
            self.assertEqual(reader[0]["Idade"], "30")
            self.assertEqual(reader[0]["Número da Camisa"], "14")
            self.assertEqual(reader[1]["Id do Jogador"], "FLU-10")

if __name__ == "__main__":
    unittest.main()
