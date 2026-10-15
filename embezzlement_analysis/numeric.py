"""Exact decimal validation with explicit resource and precision limits."""

from decimal import Decimal, InvalidOperation


def positive_bounded_decimal(value, field):
    """Return a finite positive Decimal within the supported exact domain.

    The Decimal coefficient may contain at most 38 digits (including trailing
    zeros), its stored exponent must be at least -18, and its adjusted exponent
    must be at most 37 (value strictly below 1e38). Values are rejected rather
    than rounded or normalized. Check these bounds before Fraction conversion
    or storage: a compact input such as 1e1000000000 must never expand into a
    billion-digit integer. Booleans are not numeric inputs.
    """
    message = field + ' must be a finite positive decimal'
    if isinstance(value, bool):
        raise ValueError(message)
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(message) from None
    if not number.is_finite() or number <= 0:
        raise ValueError(message)
    representation = number.as_tuple()
    if (len(representation.digits) > 38 or representation.exponent < -18
            or number.adjusted() > 37):
        raise ValueError(field + ' exceeds decimal limits: coefficient <=38 digits, '
                         'exponent >=-18, and magnitude <1e38')
    return number
