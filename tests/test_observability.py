import io
import logging
import sqlite3
import unittest
from unittest.mock import patch

from app.observability import configure_logging, error_category, log_failure
from app.ui.error_messages import safe_error_message


class ObservabilityTests(unittest.TestCase):
    def test_error_categories_are_based_on_type(self) -> None:
        self.assertEqual(error_category(sqlite3.OperationalError("private sql")), "database")
        self.assertEqual(error_category(PermissionError("private user")), "authorization")
        self.assertEqual(error_category(ValueError("bad quantity")), "validation")

    def test_failure_log_omits_exception_message(self) -> None:
        logger = logging.getLogger("app")
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logger.addHandler(handler)
        try:
            try:
                raise RuntimeError("password=very-secret /private/path/accounts.sqlite3")
            except RuntimeError as error:
                log_failure("test_failure", error)
        finally:
            logger.removeHandler(handler)
        self.assertIn("category=unexpected", stream.getvalue())
        self.assertNotIn("very-secret", stream.getvalue())
        self.assertNotIn("accounts.sqlite3", stream.getvalue())

    def test_ui_hides_internal_messages_and_preserves_validation(self) -> None:
        internal = sqlite3.OperationalError("/private/path/db locked")
        self.assertEqual(safe_error_message(internal, "Please retry."), "Please retry.")
        self.assertEqual(
            safe_error_message(ValueError("Choose a valid quantity."), "Retry.", allow_value_error=True),
            "Choose a valid quantity.",
        )

    def test_logging_configuration_is_idempotent(self) -> None:
        logger = logging.getLogger("app")
        original_level = logger.level
        self.addCleanup(logger.setLevel, original_level)
        with patch.dict("os.environ", {"SHOPWISE_LOG_LEVEL": "DEBUG"}):
            configure_logging()
            count = len(logger.handlers)
            configure_logging()
        self.assertEqual(len(logger.handlers), count)
        self.assertEqual(logger.level, logging.DEBUG)
