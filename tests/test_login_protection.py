import unittest

from app.shopping import login_protection


class LoginProtectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.email = "limit-test@example.com"
        login_protection.clear_login_failures(self.email)

    def tearDown(self) -> None:
        login_protection.clear_login_failures(self.email)

    def test_failed_attempts_are_limited_for_a_cooldown_window(self) -> None:
        for attempt in range(login_protection.MAX_FAILURES):
            login_protection.record_login_failure(self.email, now=100 + attempt)
        self.assertFalse(login_protection.login_allowed(self.email, now=105))
        self.assertTrue(
            login_protection.login_allowed(
                self.email,
                now=104 + login_protection.WINDOW_SECONDS,
            )
        )

    def test_success_can_clear_attempts_and_email_matching_is_normalized(self) -> None:
        for attempt in range(login_protection.MAX_FAILURES):
            login_protection.record_login_failure(self.email, now=200 + attempt)
        login_protection.clear_login_failures(" LIMIT-TEST@example.com ")
        self.assertTrue(login_protection.login_allowed(self.email, now=205))


if __name__ == "__main__":
    unittest.main()
