import re

_OFF_TOPIC_REQUEST = re.compile(
    r"cover\s*letter"
    r"|r[ée]sum[ée]"
    r"|\bcv\b"
    r"|curriculum\s+vitae"
    r"|\bcareer\w*\b"
    r"|\bjob\s*(?:search|hunt|listing|opening|application|as\b)"
    r"|(?:search|find|found|look|hunt|apply|applying|land|get|got)\w*\s+(?:\w+\s+){0,4}jobs?\b"
    r"|\bhiring\b|\brecruit\w+|\binternship\w*"
    r"|\binterview\s+(?:prep|preparation|question|tip)"
    r"|\bhomework\b|\bessay\b|\bassignment\b"
    r"|\bwrite\s+(?:me\s+)?(?:a\s+|an\s+|the\s+)?(?:code|program|script|function|essay|paragraph)"
    r"|\bdebug\b|\bfix\s+(?:my|this|the)\s+code"
    r"|\bphilosoph\w*|meaning\s+of\s+life"
    r"|\bcars?\b|\bvehicles?\b|\bbikes?\b|\bscoot(?:er|y|ers|ies)\b|\bautomobiles?\b"
    r"|\bflights?\b|\bair(?:line|fare|ticket)s?\b|\btrains?\b|\bbus(?:es)?\s+tickets?\b"
    r"|\bhotels?\b|\btravel\s+(?:bookings?|packages?|deals?)"
    r"|\breal\s+estate\b|\bproperties\b|\bflats?\b|\bapartments?\b|\bhous(?:e|es|ing)\b|\bplots?\b"
    r"|\brestaurants?\b|\bfood\s+(?:delivery|order(?:ing)?)\b|\border\s+(?:me\s+)?food\b"
    r"|\bmovie\s+tickets?\b|\bevent\s+tickets?\b|\bconcert\s+tickets?\b",
    re.IGNORECASE,
)

_OFF_TOPIC_ANSWER = re.compile(
    r"cover\s*letter"
    r"|dear\s+(?:hiring\s+manager|sir|madam)"
    r"|to\s+whom\s+it\s+may\s+concern"
    r"|\[your\s+(?:name|phone|email|address)\]"
    r"|hiring\s+manager"
    r"|curriculum\s+vitae"
    r"|best\s+of\s+luck[^.]*\b(?:job|role|career|interview|application)",
    re.IGNORECASE,
)

_OFF_TOPIC_REFUSAL = (
    "I'm the Shopwise shopping assistant, so I can only help with shopping "
    "and questions about the Shopwise product catalog. Shopwise sells tech "
    "products across categories like Audio, Gaming, Monitors & Displays, "
    "Smart Home, Cables & Chargers, and Wearables & Mobile. Let me know if "
    "you'd like help finding a product!"
)

_GENERIC_FILLER = re.compile(
    r"^\s*(?:"
    r"as\s+an?\s+(?:ai|artificial\s+intelligence|language\s+model|assistant)[^.!\n]*[.!]?"
    r"|glad\s+i\s+could\s+help[^.!\n]*[.!]?"
    r"|i'?m\s+(?:just\s+)?an?\s+(?:ai|language\s+model)[^.!\n]*[.!]?"
    r")\s*",
    re.IGNORECASE,
)


def is_off_topic_request(message: str) -> bool:
    return bool(_OFF_TOPIC_REQUEST.search(message))


def contains_off_topic_content(answer: str) -> bool:
    return bool(_OFF_TOPIC_ANSWER.search(answer))


def ground_chat_answer(answer: str, user_message: str = "") -> str:
    marker = "Catalog results from shopping.db:"
    if marker in answer:
        results = answer.split(marker, maxsplit=1)[1].strip()
        return f"Here are the catalog results for your request:\n\n{results}"

    if answer.strip() == "What is your maximum budget in rupees?":
        return answer

    if is_off_topic_request(user_message) or contains_off_topic_content(answer):
        return _OFF_TOPIC_REFUSAL

    answer = _GENERIC_FILLER.sub("", answer, count=1).strip()

    if answer and not contains_unverified_product_claim(answer):
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
