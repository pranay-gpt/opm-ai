# Preprocessing module for PVT and rock-property pipeline.
# Provides correlation functions, table builders, and validators.

# Fluid descriptor (opm_ai/preprocess/models.py)

The dataclass `FluidDescriptor` is the user-facing shape that
flows from the API / builder into the table builders. Fields:
api_gravity, gas_specific_gravity, gor, reservoir_temp_f|c,
salinity_ppm, pressure_range_psi, unit_system, and (as of
2026-08-04) `correlation: CorrelationName` defaulting to
"Standing". Allowed values: Standing, VasquezBeggs, AlMarhoun.
LET/Corey are out of scope for this field (relperm families,
not PVT correlations). Validation in __post_init__.

The `correlation` field is what `_select_oil_correlation` in
pvt_builder.py honors when no explicit `correlations` dict is
passed by the caller. Standalone callers that pass `correlations={}`
(empty dict) bypass the descriptor and go through `recommend_correlation`
instead - by design, so the LLM advisor stays reachable.