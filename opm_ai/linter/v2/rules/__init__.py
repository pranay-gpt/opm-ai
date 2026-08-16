"""v2 linter rule families.

Each module below registers one or more rules via
`opm_ai.linter.v2.validator.register`. Rules are dispatched by code
range:

- shape.py           L200-L209 (record/item-shape checks)
- crossref.py        L220-L229 (well/group/region cross-references)
- dims.py            L230-L239 (dimension consistency)
- requires.py        L240-L249 (requires/prohibits)
- section.py         L260-L269 (section presence)
- opm.py             L270-L279 (OPM Flow specific)
- parse.py           L160-L169 (parse-level errors surfaced as INFO)
- section_validity.py L170-L179 (section-mismatch / unknown keyword)

L210-L219 (value-range), L250-L259 (UDQ-specific), and L261
(section order) are reserved ranges for future rules. Adding a new
family means creating a module here and adding it to the imports.
"""

from . import crossref  # noqa: F401
from . import dims  # noqa: F401
from . import opm  # noqa: F401
from . import parse  # noqa: F401
from . import requires  # noqa: F401
from . import section  # noqa: F401
from . import section_validity  # noqa: F401
from . import shape  # noqa: F401