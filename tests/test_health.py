import os
import unittest
from unittest.mock import patch

import app.db.schema as schema
from app.health import collect_health_checks
from tests.database_fixture import create_shopwise_databases


class HealthCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.shopping_db, self.account_db = create_shopwise_databases(self)
        self.schema_path = patch.object(schema, "DB_PATH", self.shopping_db)
        self.schema_path.start()
        self.addCleanup(self.schema_path.stop)
        self.auth_path = patch.dict(
            os.environ, {"SHOPPING_AUTH_DB": str(self.account_db)}
        )
        self.auth_path.start()
        self.addCleanup(self.auth_path.stop)
        self.dotenv = patch("app.health.load_dotenv")
        self.dotenv.start()
        self.addCleanup(self.dotenv.stop)

    def test_ready_databases_and_runtime_report_healthy(self) -> None:
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-only-key"}):
            overall, checks = collect_health_checks()

        self.assertEqual(overall, "healthy")
        statuses = {check.name: check.status for check in checks}
        self.assertEqual(statuses["Shopping database"], "healthy")
        self.assertEqual(statuses["Accounts database"], "healthy")
        self.assertEqual(statuses["MCP subprocess"], "not_checked")
        self.assertNotIn("test-only-key", repr(checks))

    def test_missing_gemini_configuration_is_degraded_not_unhealthy(self) -> None:
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            overall, checks = collect_health_checks()

        self.assertEqual(overall, "degraded")
        gemini = next(check for check in checks if check.name == "Gemini configuration")
        self.assertEqual(gemini.status, "degraded")
        self.assertIn("shopping remains available", gemini.message)

    def test_database_failure_is_safe_and_unhealthy(self) -> None:
        with (
            patch(
                "app.health.validate_shopping_schema",
                side_effect=RuntimeError("secret path and private database details"),
            ),
            patch("app.health.log_failure") as log_failure,
        ):
            overall, checks = collect_health_checks()

        shopping = next(check for check in checks if check.name == "Shopping database")
        self.assertEqual(overall, "unhealthy")
        self.assertEqual(shopping.status, "unhealthy")
        self.assertNotIn("private database details", shopping.message)
        log_failure.assert_called_once()


if __name__ == "__main__":
    unittest.main()
