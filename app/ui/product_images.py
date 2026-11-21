from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_IMAGE_DIRECTORY = PROJECT_ROOT / "assets" / "images" / "products"


PRODUCT_IMAGES_BY_ID: dict[int, str] = {
    100: "logitech-g502.png",
    64: "kingston-nvme-ssd.jpg",
    81: "tp-wa855re.jpg",
    80: "tp-c1200.jpg",
    53: "samsung-buds.png",
    60: "samsung-t7.jpg",
}

PRODUCT_IMAGES_BY_NAME: dict[str, str] = {
    "Logitech RGB Gaming Mouse": "logitech-g502.png",
    "Kingston 500GB NVMe SSD": "kingston-nvme-ssd.jpg",
    "TP-Link N300 Wi-Fi Range Extender": "tp-wa855re.jpg",
    "TP-Link AC1200 Dual Band Wi-Fi Router": "tp-c1200.jpg",
    "Samsung Galaxy Buds True Wireless Earbuds": "samsung-buds.png",
    "Samsung 500GB Portable SSD": "samsung-t7.jpg",
}


def get_product_image_path(product: dict) -> Path | None:
    product_id = product.get("id")
    filename = PRODUCT_IMAGES_BY_ID.get(product_id)
    if filename is None:
        filename = PRODUCT_IMAGES_BY_NAME.get(str(product.get("name") or "").strip())
    if filename is None:
        return None
    path = PRODUCT_IMAGE_DIRECTORY / filename
    return path if path.is_file() else None

