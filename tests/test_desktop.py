import unittest
from unittest.mock import patch

from desktop import DesktopAPI, resource_path


class DesktopTests(unittest.TestCase):
    def test_dashboard_is_bundled_as_inline_html(self):
        page = resource_path("ui/index.html").read_text(encoding="utf-8")
        self.assertIn("window.pywebview.api", page)
        self.assertIn("데이터 연결", page)
        self.assertNotIn('<script src="https://', page)

    def test_initial_state_needs_no_network_or_server(self):
        state = DesktopAPI().get_initial_state()
        self.assertFalse(state["has_data"])
        self.assertEqual(state["data_status"], "데이터 연결 전")

    def test_demo_uses_bundled_synthetic_data(self):
        result = DesktopAPI().load_demo()
        self.assertTrue(result["ok"])
        self.assertEqual(result["data_source"], "합성 예시 데이터")
        self.assertGreater(result["bar_count"], 0)

    @patch("desktop.keyring.set_password")
    @patch("desktop.keyring.get_password")
    @patch("desktop.TossMarketClient")
    def test_connection_uses_saved_credentials_when_inputs_are_blank(
        self, client_class, get_password, _set_password
    ):
        get_password.side_effect = lambda service, name: {
            "toss_client_id": "saved-id",
            "toss_client_secret": "saved-secret",
        }[name]
        result = DesktopAPI().test_connection("", "")
        self.assertTrue(result["ok"])
        client_class.assert_called_once_with("saved-id", "saved-secret")
        client_class.return_value.test_connection.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
