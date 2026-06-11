import unittest

from paper_recommender.email_delivery import (
    build_email_message,
    send_email_message_with_retries,
    should_send_digest,
)


class EmailDeliveryTests(unittest.TestCase):
    def test_build_email_message_sets_headers_and_html_body(self):
        message = build_email_message(
            subject="Daily Recommendations",
            sender="sender@example.com",
            receiver="receiver@example.com",
            html="<h1>Hello</h1>",
        )

        self.assertEqual(message["Subject"], "Daily Recommendations")
        self.assertEqual(message["From"], "sender@example.com")
        self.assertEqual(message["To"], "receiver@example.com")
        self.assertEqual(message.get_content_type(), "text/html")
        self.assertIn("<h1>Hello</h1>", message.get_content())

    def test_should_skip_empty_digest_by_default(self):
        self.assertFalse(should_send_digest({"recommendations": []}))
        self.assertTrue(should_send_digest({"recommendations": []}, send_empty=True))
        self.assertTrue(should_send_digest({"recommendations": [{"paper_id": "p1"}]}))

    def test_send_email_message_with_retries_until_success(self):
        message = build_email_message("Daily", "sender@example.com", "receiver@example.com", "<p>Hi</p>")
        calls = []
        sleeps = []

        def flaky_sender(**kwargs):
            calls.append(kwargs["smtp_host"])
            if len(calls) < 3:
                raise OSError("temporary smtp failure")

        attempts = send_email_message_with_retries(
            message,
            smtp_host="smtp.example.com",
            smtp_port=465,
            username="sender@example.com",
            password="secret",
            attempts=3,
            send_func=flaky_sender,
            sleep_func=sleeps.append,
        )

        self.assertEqual(attempts, 3)
        self.assertEqual(calls, ["smtp.example.com", "smtp.example.com", "smtp.example.com"])
        self.assertEqual(sleeps, [1.0, 2.0])

    def test_send_email_message_with_retries_raises_after_exhaustion(self):
        message = build_email_message("Daily", "sender@example.com", "receiver@example.com", "<p>Hi</p>")

        def failing_sender(**kwargs):
            raise OSError("smtp is down")

        with self.assertRaisesRegex(OSError, "smtp is down"):
            send_email_message_with_retries(
                message,
                smtp_host="smtp.example.com",
                smtp_port=465,
                username="sender@example.com",
                password="secret",
                attempts=2,
                send_func=failing_sender,
                sleep_func=lambda seconds: None,
            )


if __name__ == "__main__":
    unittest.main()
