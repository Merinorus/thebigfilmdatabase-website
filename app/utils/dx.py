from app.utils.string import _remove_double_spaces


def parse_dx_code(dx_code: str, max_digits=6) -> str | None:
    """Stringify a DX code number if provided. Return a string or None."""
    if not dx_code:
        return None
    result = int(dx_code)
    result = str(result).zfill(max_digits)
    if len(result) > max_digits:
        raise ValueError(f"Length should be lower or equal than {max_digits}")
    return result


def two_parts_dx_number_to_dx_extract(dx_number: str) -> str | None:
    """
    Extract the two parts of a given DX number and convert it to a DX extract. Add leading 0 if necessary.

    Examples:
    - "162-2" -> 162 * 16 + 2 = "2594"
    - "7-0"   ->   7 * 16 + 0 = "0112"
    """
    if not dx_number:
        return None
    # "-" should be the separator, but we accept other just in case
    try:
        accepted_separators = ["-", " ", "/"]
        for pattern in accepted_separators:
            dx_number = dx_number.replace(pattern, " ")
        dx_number = _remove_double_spaces(dx_number)
        dx_parts = dx_number.split(" ")
        if len(dx_parts) < 2:
            raise ValueError()
        dx_part_1 = int(dx_parts[0])
        dx_part_2 = int(dx_parts[1])
        return str(16 * dx_part_1 + dx_part_2).zfill(4)
    except Exception as e:
        raise ValueError(
            'Invalid DX number. The accepted format is two series of digits separated by a dash. "XXX-XX"'
        ) from e


def dx_extract_to_two_part_dx_number(dx_extract: str) -> str | None:
    """Convert a 4-digit long DX extract to its DX number equivalent in "XXX-YY" format.
        XXX (digits) is the DX number part 1 (product code),
        YY  (digits) is the DX number part 2 (generation code).

    Args:
        dx_extract (str): the DX extract (four digits)

    Returns:
        str | None: The DX number, if a valid DX extract has been provided, else None
    """
    if not dx_extract:
        return None
    try:
        dx_extract = int(dx_extract)
        if dx_extract < 16:
            raise ValueError("DX extract value should be at least 16")
        if dx_extract > 2047:
            raise ValueError("DX extract value should be at most 2047")
        dx_part_1 = dx_extract // 16
        dx_part_2 = dx_extract % 16
        return f"{dx_part_1}-{dx_part_2}"
    except Exception:
        # Silently fail
        return None
