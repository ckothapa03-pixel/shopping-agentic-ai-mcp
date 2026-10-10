from app.db.products import find_products

results = find_products(
    search_term="mouse",
    max_price=1000,
    min_rating=4,
    in_stock=True,
)

print(f"Found {len(results)} product(s):")
for product in results:
    print(product)
