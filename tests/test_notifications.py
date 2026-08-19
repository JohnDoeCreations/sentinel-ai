import unittest
from unittest.mock import Mock, patch

from utils.notifications import send_alert_email


class NotificationTests(unittest.TestCase):
    @patch("utils.notifications.requests.post")
    def test_sends_one_digest_for_new_triggers(self, post):
        response = Mock()
        response.json.return_value = {"id": "email-123"}
        post.return_value = response

        result = send_alert_email(
            [{"symbol": "AAPL", "message": "AAPL reached $200."}],
            api_key="test-key",
            recipient="owner@example.com",
        )

        self.assertEqual(result, "email-123")
        post.assert_called_once()
        response.raise_for_status.assert_called_once()
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["to"], ["owner@example.com"])
        self.assertIn("AAPL reached $200.", payload["html"])

    @patch("utils.notifications.requests.post")
    def test_does_not_send_empty_digest(self, post):
        self.assertIsNone(
            send_alert_email([], api_key="test-key", recipient="owner@example.com")
        )
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
