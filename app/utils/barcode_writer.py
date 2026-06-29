import zxingcpp


def _remove_background(svg_barcode: str):
    return svg_barcode.replace('fill="#FFFFFF"', 'fill="#FFFFFF00"', 1)


def generate_dx_film_edge_barcode(input: str, scale: int = None, add_quiet_zones: bool = True):
    """Return the DX film edge barcode for the given input.

    Expected formats examples:
    - Without frame number: "79-2" or "1266"
    - With frame number: "79-2/10A" or "1266/10A"

    Returns:
        the DX film edge barcode, as SVG
    """
    try:
        barcode = zxingcpp.create_barcode(input, zxingcpp.BarcodeFormat.DXFilmEdge)
    except ValueError:
        return None
    svg = zxingcpp.write_barcode_to_svg(barcode, scale, add_quiet_zones=add_quiet_zones)
    return _remove_background(svg)
