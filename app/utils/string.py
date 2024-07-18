def _remove_double_spaces(text: str) -> str | None:
    """Remove any multiple following space in a string."""
    if not isinstance(text, str):
        return None
    result = ""
    while result != text:
        result = text
        text = text.replace("  ", " ")
    return result
