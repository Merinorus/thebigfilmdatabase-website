import zxingcpp


def _remove_background(svg_barcode: str):
    return svg_barcode.replace('fill="#FFFFFF"', 'fill="#FFFFFF00"', 1)


def generate_dx_film_edge_barcode(input: str, size_hint: int = None, with_quiet_zones: bool = True):
    """Return the DX film edge barcode for the given input.

    The frame number is optional.

    Args:
        frame_number (str | None, optional): Frame number. Defaults to None.

    Returns:
        the DX film edge barcode, as SVG
    """
    try:
        barcode = zxingcpp.create_barcode(input, zxingcpp.BarcodeFormat.DXFilmEdge)
    except ValueError:
        return None
    svg = zxingcpp.write_barcode_to_svg(barcode, size_hint, with_quiet_zones=with_quiet_zones)
    return _remove_background(svg)
