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
