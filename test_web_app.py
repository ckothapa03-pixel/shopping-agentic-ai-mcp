import unittest

from app.web_app import _ground_chat_answer


class GroundedChatAnswerTests(unittest.TestCase):
    def test_displays_catalog_results_without_model_product_claims(self) -> None:
        answer = (
            "A model-generated product claim. "
            "Catalog results from shopping.db:\n"
            "- Real catalog item | ₹500.00 | Rating: 4.5/5"
        )

        grounded = _ground_chat_answer(answer)

        self.assertNotIn("model-generated", grounded)
        self.assertIn("Real catalog item", grounded)
        self.assertIn("₹500.00", grounded)

    def test_preserves_budget_clarification(self) -> None:
        self.assertEqual(
            _ground_chat_answer("What is your maximum budget in rupees?"),
            "What is your maximum budget in rupees?",
        )

    def test_rejects_product_claims_without_catalog_results(self) -> None:
        grounded = _ground_chat_answer("Buy the SuperMouse for ₹500.")

        self.assertNotIn("SuperMouse", grounded)
        self.assertIn("couldn't verify product matches", grounded)


if __name__ == "__main__":
    unittest.main()
