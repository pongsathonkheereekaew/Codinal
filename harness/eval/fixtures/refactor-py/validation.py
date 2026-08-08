def validate_user(data):
    if not data.get("name"):
        raise ValueError("name required")
    if len(data.get("name", "")) < 2:
        raise ValueError("name too short")
    if not data.get("email"):
        raise ValueError("email required")
    if "@" not in data.get("email", ""):
        raise ValueError("email invalid")


def validate_order(data):
    if not data.get("id"):
        raise ValueError("id required")
    if len(data.get("id", "")) < 2:
        raise ValueError("id too short")
    if not data.get("sku"):
        raise ValueError("sku required")
    if len(data.get("sku", "")) < 2:
        raise ValueError("sku too short")
