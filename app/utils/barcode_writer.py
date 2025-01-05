from enum import StrEnum
from io import BytesIO

import zxingcpp
from PIL import Image


def _remove_background(svg_barcode: str):
    return svg_barcode.replace('fill="#FFFFFF"', 'fill="#FFFFFF00"', 1)


class BarcodeFormat(StrEnum):
    PNG = "png"
    SVG = "svg"


def generate_dx_film_edge_barcode(
    input: str, size_hint: int = None, with_quiet_zones: bool = True, format: BarcodeFormat = BarcodeFormat.SVG
):
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
    if format == BarcodeFormat.SVG:
        svg = zxingcpp.write_barcode_to_svg(barcode, size_hint, with_quiet_zones=with_quiet_zones)
        return _remove_background(svg)
    elif format == BarcodeFormat.PNG:
        img = zxingcpp.write_barcode_to_image(barcode, size_hint, with_quiet_zones=with_quiet_zones)
        buffer = BytesIO()
        image = Image.fromarray(img)
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer
    else:
        raise ValueError(f"Invalid format: {format}")
