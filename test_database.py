from app.tools.products_tool import search_products

results = search_products(
    search_term="",
    max_price=1000,
)

print(f"Found {len(results)} product(s) priced at ₹1,000 or less:")
for product in results:
    print(
        f"{product['name']} | ₹{product['price']:.2f} | "
        f"Rating: {product['rating_avg']} | Stock: {product['stock']} | "
        f"Brand: {product['brand']} | Category: {product['category']}"
    )
if not results:
    print("No matching products.")
