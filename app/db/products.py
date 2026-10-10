from app.db.database import get_connection


def find_products(
    search_term: str = "",
    max_price: float | None = None,
    min_rating: float | None = None,
    in_stock: bool = False,
    limit: int = 20,
) -> list[dict]:
    """
    Search products in the local shopping database.

    Search checks product name and description.
    Optional filters:
      - max_price
      - min_rating
      - in_stock
    """
    search_term = (search_term or "").strip()

    query = """
        SELECT
            p.id,
            p.sku,
            p.name,
            p.description,
            p.price,
            p.mrp,
            p.stock,
            p.rating_avg,
            p.rating_count,
            c.name AS category,
            b.name AS brand
        FROM products p
        LEFT JOIN categories c ON c.id = p.category_id
        LEFT JOIN brands b ON b.id = p.brand_id
        WHERE 1 = 1
    """

    params = []

    if search_term:
        query += """
            AND (
                LOWER(p.name) LIKE LOWER(?)
                OR LOWER(p.description) LIKE LOWER(?)
                OR LOWER(p.sku) LIKE LOWER(?)
                OR LOWER(COALESCE(b.name, '')) LIKE LOWER(?)
                OR LOWER(COALESCE(c.name, '')) LIKE LOWER(?)
            )
        """
        term = f"%{search_term}%"
        params.extend([term, term, term, term, term])

    if max_price is not None:
        query += " AND p.price <= ?"
        params.append(max_price)

    if min_rating is not None:
        query += " AND p.rating_avg >= ?"
        params.append(min_rating)

    if in_stock:
        query += " AND p.stock > 0"

    query += """
        ORDER BY p.rating_avg DESC, p.rating_count DESC, p.price ASC
        LIMIT ?
    """
    params.append(limit)

    with get_connection() as connection:
        rows = connection.execute(query, params).fetchall()

    return [dict(row) for row in rows]
