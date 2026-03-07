import unittest
from llm.parser import resolve_account


ACCOUNTS = [
    {'account_id': 'Cash'},
    {'account_id': 'Visa Pichincha'},
    {'account_id': 'Visa Produbanco'},
    {'account_id': 'Diners'},
]


class TestResolveAccount(unittest.TestCase):

    # --- Empty / invalid values default to Cash ---

    def test_none_defaults_to_cash(self):
        self.assertEqual(resolve_account(None, ACCOUNTS), "Cash")

    def test_empty_string_defaults_to_cash(self):
        self.assertEqual(resolve_account("", ACCOUNTS), "Cash")

    def test_na_defaults_to_cash(self):
        self.assertEqual(resolve_account("N/A", ACCOUNTS), "Cash")

    def test_none_string_defaults_to_cash(self):
        self.assertEqual(resolve_account("none", ACCOUNTS), "Cash")

    def test_null_string_defaults_to_cash(self):
        self.assertEqual(resolve_account("null", ACCOUNTS), "Cash")

    def test_whitespace_defaults_to_cash(self):
        self.assertEqual(resolve_account("   ", ACCOUNTS), "Cash")

    # --- Exact match ---

    def test_exact_match(self):
        self.assertEqual(resolve_account("Cash", ACCOUNTS), "Cash")

    def test_exact_match_visa(self):
        self.assertEqual(resolve_account("Visa Pichincha", ACCOUNTS), "Visa Pichincha")

    # --- Case-insensitive match ---

    def test_case_insensitive_cash(self):
        self.assertEqual(resolve_account("cash", ACCOUNTS), "Cash")

    def test_case_insensitive_upper(self):
        self.assertEqual(resolve_account("DINERS", ACCOUNTS), "Diners")

    def test_case_insensitive_mixed(self):
        self.assertEqual(resolve_account("visa pichincha", ACCOUNTS), "Visa Pichincha")

    # --- Substring / partial match ---

    def test_partial_pichincha(self):
        self.assertEqual(resolve_account("pichincha", ACCOUNTS), "Visa Pichincha")

    def test_partial_produbanco(self):
        self.assertEqual(resolve_account("produbanco", ACCOUNTS), "Visa Produbanco")

    def test_partial_diners(self):
        self.assertEqual(resolve_account("diners", ACCOUNTS), "Diners")

    def test_partial_visa(self):
        # "visa" is a substring of both Visa Pichincha and Visa Produbanco,
        # should return the first match
        result = resolve_account("visa", ACCOUNTS)
        self.assertIn(result, ["Visa Pichincha", "Visa Produbanco"])

    # --- Unrecognized values default to Cash ---

    def test_garbage_defaults_to_cash(self):
        self.assertEqual(resolve_account("garbage", ACCOUNTS), "Cash")

    def test_random_string_defaults_to_cash(self):
        self.assertEqual(resolve_account("my bank account", ACCOUNTS), "Cash")

    # --- Custom default ---

    def test_custom_default(self):
        self.assertEqual(resolve_account("garbage", ACCOUNTS, default="Diners"), "Diners")

    def test_na_with_custom_default(self):
        self.assertEqual(resolve_account("N/A", ACCOUNTS, default="Diners"), "Diners")

    # --- Edge: whitespace around value ---

    def test_leading_trailing_whitespace(self):
        self.assertEqual(resolve_account("  Cash  ", ACCOUNTS), "Cash")

    def test_whitespace_partial(self):
        self.assertEqual(resolve_account("  pichincha  ", ACCOUNTS), "Visa Pichincha")

    # --- Edge: empty accounts list ---

    def test_empty_accounts_returns_default(self):
        self.assertEqual(resolve_account("anything", [], default="Cash"), "Cash")


if __name__ == "__main__":
    unittest.main()
