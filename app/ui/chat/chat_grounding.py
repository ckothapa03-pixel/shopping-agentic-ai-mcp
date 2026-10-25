def ground_chat_answer(answer: str, user_message: str = "") -> str:
    marker = "Catalog results from shopping.db:"
    if marker in answer:
        results = answer.split(marker, maxsplit=1)[1].strip()
        return f"Here are the catalog results for your request:\n\n{results}"

    if answer.strip() == "What is your maximum budget in rupees?":
        return answer

    if answer.strip() and not contains_unverified_product_claim(answer):
        return answer

    return (
        "I couldn't verify product matches from the catalog. Try asking for "
        "a product type, rating, stock status, or maximum budget."
    )


def contains_unverified_product_claim(answer: str) -> bool:
    lowered = answer.casefold()
    return any(
        marker in lowered
        for marker in ("₹", "in stock", "out of stock", "available for", "buy the ")
    )
