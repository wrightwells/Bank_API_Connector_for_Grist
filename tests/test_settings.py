import unittest
from unittest.mock import patch

from grist_finance_connector.config.settings import Settings
from grist_finance_connector.config.settings import load_settings


class SettingsTests(unittest.TestCase):
    @patch.dict(
        "os.environ",
        {
            "GRIST_BASE_URL": "http://grist:8484",
            "GRIST_DOC_ID": "doc123",
            "GRIST_API_KEY": "secret",
            "SOURCE_BASE_URL": "https://api.example.com",
            "SOURCE_API_KEY": "provider-secret",
        },
        clear=True,
    )
    def test_load_settings_reads_required_values(self) -> None:
        settings = load_settings()

        self.assertIsInstance(settings, Settings)
        self.assertEqual(settings.grist_doc_id, "doc123")
        self.assertEqual(settings.source_base_url, "https://api.example.com")
        self.assertEqual(settings.source_auth_method, "api_key")

    @patch.dict(
        "os.environ",
        {
            "GRIST_BASE_URL": "http://grist:8484",
            "GRIST_DOC_ID": "doc123",
            "GRIST_API_KEY": "secret",
            "SOURCE_BASE_URL": "https://api.example.com",
        },
        clear=True,
    )
    def test_api_key_auth_requires_secret(self) -> None:
        with self.assertRaises(ValueError):
            load_settings()

    @patch.dict(
        "os.environ",
        {
            "SOURCE_PROVIDER": "starling",
            "SOURCE_NAME": "starling_bank",
            "STARLING_ACCESS_TOKEN": "token",
            "GRIST_BASE_URL": "http://grist:8484",
            "GRIST_DOC_ID": "doc123",
            "GRIST_API_KEY": "secret",
        },
        clear=True,
    )
    def test_starling_provider_uses_starling_specific_secret(self) -> None:
        settings = load_settings()

        self.assertEqual(settings.source_provider, "starling")
        self.assertEqual(settings.starling_access_token, "token")
        self.assertEqual(settings.effective_starling_access_tokens, ("token",))

    @patch.dict(
        "os.environ",
        {
            "SOURCE_PROVIDER": "starling",
            "SOURCE_NAME": "starling_bank",
            "STARLING_ACCESS_TOKENS": "token-a, token-b , token-c",
            "STARLING_ACCOUNT_UIDS": "acc-1,acc-2",
            "GRIST_BASE_URL": "http://grist:8484",
            "GRIST_DOC_ID": "doc123",
            "GRIST_API_KEY": "secret",
        },
        clear=True,
    )
    def test_starling_provider_supports_multiple_tokens_and_account_filters(self) -> None:
        settings = load_settings()

        self.assertEqual(settings.effective_starling_access_tokens, ("token-a", "token-b", "token-c"))
        self.assertEqual(settings.effective_starling_account_uids, ("acc-1", "acc-2"))


if __name__ == "__main__":
    unittest.main()
