"""v2 linter rule families.

Each module below registers one or more rules via
`opm_ai.linter.v2.validator.register`. Rules are dispatched by code
range:

- shape.py       L200-L209 (record/item-shape checks)
- range.py       L210-L219 (value-range checks)
- crossref.py    L220-L229 (well/group/region cross-references)
- dims.py        L230-L239 (dimension consistency)
- requires.py    L240-L249 (requires/prohibits)
- udq.py         L250-L259 (UDQ-specific)
- section.py     L260-L269 (section order / presence)
- opm.py         L270-L279 (OPM Flow specific)
"""

from . import crossref  # noqa: F401
from . import dims  # noqa: F401
from . import opm  # noqa: F401
from . import requires  # noqa: F401
from . import section  # noqa: F401
from . import shape  # noqa: F401