import unittest
from normalizers import (
    validate_date,
    format_colors,
    format_nullable_string,
    format_number_field,
    is_valid_championship
)

class TestNormalizers(unittest.TestCase):

    def test_validate_date(self):
        # Válidas
        self.assertEqual(validate_date("1910-09-01"), "1910-09-01")
        self.assertEqual(validate_date(" 2024-01-18 "), "2024-01-18")
        
        # Inválidas / Formato incorreto
        self.assertEqual(validate_date("01/09/1910"), "")
        self.assertEqual(validate_date("2024-02-30"), "")  # Data inexistente
        self.assertEqual(validate_date("texto_invalido"), "")
        self.assertEqual(validate_date(""), "")
        self.assertEqual(validate_date(None), "")
        self.assertEqual(validate_date(19100901), "")

    def test_format_colors(self):
        # Casos normais
        self.assertEqual(format_colors(["preto", "branco"]), "preto|branco")
        self.assertEqual(format_colors(["  azul  ", " branco "]), "azul|branco")
        self.assertEqual(format_colors(["azul", "branco", "vermelho"]), "azul|branco|vermelho")

        # Casos de borda
        self.assertEqual(format_colors([]), "")
        self.assertEqual(format_colors(None), "")
        self.assertEqual(format_colors("verde"), "verde")
        self.assertEqual(format_colors(["preto", None, "", "   ", "branco"]), "preto|branco")

    def test_format_nullable_string(self):
        # Casos normais e nulos
        self.assertEqual(format_nullable_string("Timão"), "Timão")
        self.assertEqual(format_nullable_string("  Verdão  "), "Verdão")
        self.assertEqual(format_nullable_string(None), "")
        self.assertEqual(format_nullable_string(""), "")
        self.assertEqual(format_nullable_string(123), "123")

    def test_format_number_field(self):
        # Campos de idade, gols, número de camisa
        self.assertEqual(format_number_field(26), "26")
        self.assertEqual(format_number_field(" 10 "), "10")
        self.assertEqual(format_number_field(26.0), "26") # Float equivalente a inteiro
        self.assertEqual(format_number_field(None), "")
        self.assertEqual(format_number_field(""), "")


    def test_is_valid_championship(self):
        # Válidos (Série A e B com variações de maiúsculas, acentos e espaços)
        self.assertTrue(is_valid_championship("SERIE A"))
        self.assertTrue(is_valid_championship("SERIE B"))
        self.assertTrue(is_valid_championship("serie a"))
        self.assertTrue(is_valid_championship("Série A"))
        self.assertTrue(is_valid_championship("  SÉRIE   B  "))

        # Inválidos
        self.assertFalse(is_valid_championship("SEM CAMPEONATO"))
        self.assertFalse(is_valid_championship("SERIE C"))
        self.assertFalse(is_valid_championship(""))
        self.assertFalse(is_valid_championship(None))
        self.assertFalse(is_valid_championship(42))

if __name__ == "__main__":
    unittest.main()
