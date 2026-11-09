import unittest

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


if __name__ == "__main__":
    unittest.main()
