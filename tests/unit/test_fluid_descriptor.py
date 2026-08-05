"""Tests for FluidDescriptor dataclass validation (F2.5 audit fix).

Covers:
- NaN/Inf rejection on all finite-bounded float fields.
- Range and ordering checks (pre-existing behavior, regression guard).
- Valid construction round-trip.
"""

from __future__ import annotations

import math

import pytest

from opm_ai.preprocess.models import FluidDescriptor


class TestFluidDescriptorFiniteness:
    """F2.5 audit fix: NaN/Inf on float fields must be rejected, not silently
    propagated to correlations (where they produce non-finite PVT tables
    that the linter then flags as ERROR and the deck-builder rejects)."""

    @pytest.mark.parametrize(
        "field,value",
        [
            ("api_gravity", float("nan")),
            ("api_gravity", float("inf")),
            ("gas_specific_gravity", float("nan")),
            ("gas_specific_gravity", float("-inf")),
            ("gor", float("nan")),
            ("gor", float("inf")),
            ("salinity_ppm", float("nan")),
        ],
    )
    def test_nan_or_inf_required_field_rejected(self, field: str, value: float):
        kwargs = dict(api_gravity=30.0, gas_specific_gravity=0.7, gor=500.0)
        kwargs[field] = value
        with pytest.raises(ValueError, match="must be finite"):
            FluidDescriptor(**kwargs)

    def test_nan_optional_temperature_rejected(self):
        with pytest.raises(ValueError, match="must be finite"):
            FluidDescriptor(
                api_gravity=30.0,
                gas_specific_gravity=0.7,
                gor=500.0,
                reservoir_temp_f=float("nan"),
            )

    def test_nan_in_pressure_range_rejected(self):
        with pytest.raises(ValueError, match="must be finite"):
            FluidDescriptor(
                api_gravity=30.0,
                gas_specific_gravity=0.7,
                gor=500.0,
                pressure_range_psi=(float("nan"), 5000.0),
            )


class TestFluidDescriptorValidation:
    """Regression guard for pre-existing range/order checks (unchanged by F2.5)."""

    def test_valid_construction_round_trip(self):
        fd = FluidDescriptor(
            api_gravity=30.0,
            gas_specific_gravity=0.7,
            gor=500.0,
            reservoir_temp_f=180.0,
            salinity_ppm=5000.0,
            pressure_range_psi=(500.0, 5000.0),
            unit_system="FIELD",
            correlation="Standing",
        )
        assert fd.api_gravity == 30.0
        assert fd.gor == 500.0
        assert fd.unit_system == "FIELD"

    def test_zero_api_gravity_rejected(self):
        with pytest.raises(ValueError, match="api_gravity must be > 0"):
            FluidDescriptor(api_gravity=0.0, gas_specific_gravity=0.7, gor=500.0)

    def test_negative_gor_rejected(self):
        with pytest.raises(ValueError, match="gor must be >= 0"):
            FluidDescriptor(api_gravity=30.0, gas_specific_gravity=0.7, gor=-1.0)

    def test_pressure_range_order_rejected(self):
        with pytest.raises(ValueError, match="p_min < p_max"):
            FluidDescriptor(
                api_gravity=30.0,
                gas_specific_gravity=0.7,
                gor=500.0,
                pressure_range_psi=(5000.0, 500.0),
            )


class TestFluidDescriptorFinitenessPrecedence:
    """F2.5: the finiteness check fires before the range check, so a NaN on
    a field that ALSO has a range constraint produces the 'finite' error,
    not the range error. This locks in the diagnostic a user sees."""

    def test_nan_on_ranged_field_says_finite(self):
        with pytest.raises(ValueError, match="must be finite"):
            FluidDescriptor(
                api_gravity=float("nan"),
                gas_specific_gravity=0.7,
                gor=500.0,
            )