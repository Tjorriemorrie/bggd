"""Card sleeves: reading the card size a sleeve fits out of the name a shop printed."""

import logging
import re

logger = logging.getLogger(__name__)

# Every shop prints the size in the product name and every one of them prints it
# differently: `63x88`, `63 x 88mm`, `(57 x  57mm)`, `44mm x 67mm`, `63,5 x 88`.
# The separator is an x, the unit -- where it appears at all -- is millimetres,
# and a fraction may be written with a point or a comma. Two or three digits a
# side keeps pack counts (`2 x 50`) and micron ratings out of the match.
SLEEVE_SIZE_RE = re.compile(
    r'(?<![\d.,])(\d{2,3}(?:[.,]\d{1,2})?)\s*(?:mm)?\s*[x×*]\s*'
    r'(\d{2,3}(?:[.,]\d{1,2})?)\s*(?:mm)?(?![\d.,])',
    re.IGNORECASE,
)

# A sleeve holds a card, not a board: anything outside this range is a number
# that happened to sit next to an x.
SIZE_MIN_MM = 30
SIZE_MAX_MM = 250


def parse_sleeve_size(name: str) -> tuple[float, float] | None:
    """Read the card size in mm a sleeve fits, or None if the name is not a sized sleeve."""
    if not name or 'sleeve' not in name.casefold():
        return None
    match = SLEEVE_SIZE_RE.search(name)
    if not match:
        return None
    width, height = (float(side.replace(',', '.')) for side in match.groups())
    if not all(SIZE_MIN_MM <= side <= SIZE_MAX_MM for side in (width, height)):
        logger.info(f'Ignoring implausible sleeve size {width}x{height} in "{name}"')
        return None
    return width, height
