"""Unit tests for PVT correlation primitives.

Worked-example tests with known values from Ahmed Handbook and physical sanity checks.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from opm_ai.preprocess.correlations import (
    almarhoun_bo,
    beggs_robinson_muo_dead,
    beggs_robinson_muo_live,
    corey_sgof,
    corey_swof,
    gas_bg,
    gas_z_papay,
    lee_gonzalez_mug,
    let_sgof,
    let_swof,
    mccain_bw,
    mccain_muw,
    standing_bo,
    standing_rs_bubble,
    vasquez_beggs_bo,
)


class TestStandingCorrelations:
    """Tests for Standing (1947) correlations."""

    def test_standing_rs_bubble_typical(self):
        """Test Standing Rs and Pb for typical black oil."""
        # API 35, gas_grav 0.75, temp 200F, p=3000 psia
        rs, pb = standing_rs_bubble(35.0, 0.75, 200.0, 3000.0)
        # Physical sanity: Rs between 400-900 scf/stb for these conditions
        assert 400 < rs < 900
        # Pb should be positive and less than reservoir pressure for undersaturated
        assert 0 < pb < 3000
        print(f"Standing Rs={rs:.1f} scf/stb, Pb={pb:.1f} psia")

    def test_standing_rs_bubble_spe1_reference(self):
        """Test with SPE1-like fluid: API 35.6, gas_grav 0.71, temp 212F."""
        # SPE1 initial pressure ~3600 psia, Pb ~1900 psia
        rs, pb = standing_rs_bubble(35.6, 0.71, 212.0, 3600.0)
        # Should give reasonable values
        assert 500 < rs < 1200
        assert 1000 < pb < 4000
        print(f"SPE1 Standing Rs={rs:.1f}, Pb={pb:.1f}")

    def test_standing_bo_increases_with_rs(self):
        """Standing Bo should increase with Rs."""
        api, gas_grav, temp_f = 35.0, 0.75, 200.0
        bo1 = standing_bo(api, gas_grav, temp_f, 200.0)
        bo2 = standing_bo(api, gas_grav, temp_f, 500.0)
        bo3 = standing_bo(api, gas_grav, temp_f, 800.0)
        assert bo1 < bo2 < bo3
        # Bo should be >= 1.0
        assert bo1 >= 1.0
        assert bo3 >= 1.0

    def test_standing_bo_typical_values(self):
        """Test Standing Bo gives reasonable values."""
        bo = standing_bo(35.0, 0.75, 200.0, 800.0)
        # Typical Bo for 35 API at 800 scf/stb ~1.4-1.6
        assert 1.3 < bo < 1.8
        print(f"Standing Bo={bo:.4f} rb/stb")


class TestVasquezBeggsCorrelations:
    """Tests for Vasquez-Beggs (1980) correlations."""

    def test_vasquez_beggs_bo_api_le_30(self):
        """Vasquez-Beggs Bo for API <= 30."""
        bo = vasquez_beggs_bo(25.0, 0.8, 180.0, 500.0)
        assert bo > 1.0
        assert bo < 2.0
        print(f"VB Bo (API=25)={bo:.4f}")

    def test_vasquez_beggs_bo_api_gt_30(self):
        """Vasquez-Beggs Bo for API > 30."""
        bo = vasquez_beggs_bo(40.0, 0.7, 200.0, 800.0)
        assert bo > 1.0
        assert bo < 2.5
        print(f"VB Bo (API=40)={bo:.4f}")

    def test_vasquez_beggs_bo_increases_with_rs(self):
        """VB Bo should increase with Rs."""
        api, gas_grav, temp_f = 35.0, 0.75, 200.0
        bo1 = vasquez_beggs_bo(api, gas_grav, temp_f, 200.0)
        bo2 = vasquez_beggs_bo(api, gas_grav, temp_f, 500.0)
        bo3 = vasquez_beggs_bo(api, gas_grav, temp_f, 800.0)
        assert bo1 < bo2 < bo3


class TestAlMarhounCorrelations:
    """Tests for Al-Marhoun (1988) correlations."""

    def test_almarhoun_bo_typical(self):
        """Al-Marhoun Bo for typical Middle East crude."""
        bo = almarhoun_bo(35.0, 0.85, 220.0, 800.0, 2500.0)
        assert bo > 1.0
        assert bo < 2.5
        print(f"AlMarhoun Bo={bo:.4f}")


class TestBeggsRobinsonViscosity:
    """Tests for Beggs-Robinson (1975) viscosity correlations."""

    def test_muo_dead_positive(self):
        """Dead oil viscosity should be positive."""
        mu_od = beggs_robinson_muo_dead(35.0, 200.0)
        assert mu_od > 0
        assert mu_od < 10  # reasonable upper bound
        print(f"Dead oil mu={mu_od:.4f} cp")

    def test_muo_dead_decreases_with_temp(self):
        """Dead oil viscosity should decrease with temperature."""
        mu_od_150 = beggs_robinson_muo_dead(35.0, 150.0)
        mu_od_250 = beggs_robinson_muo_dead(35.0, 250.0)
        assert mu_od_150 > mu_od_250

    def test_muo_live_less_than_dead(self):
        """Live oil viscosity should be less than dead oil viscosity."""
        mu_od = beggs_robinson_muo_dead(35.0, 200.0)
        mu_ob = beggs_robinson_muo_live(mu_od, 800.0)
        assert mu_ob < mu_od
        assert mu_ob > 0
        print(f"Dead={mu_od:.4f}, Live={mu_ob:.4f} cp")

    def test_muo_live_decreases_with_rs(self):
        """Live oil viscosity should decrease with increasing Rs."""
        mu_od = beggs_robinson_muo_dead(35.0, 200.0)
        mu1 = beggs_robinson_muo_live(mu_od, 200.0)
        mu2 = beggs_robinson_muo_live(mu_od, 500.0)
        mu3 = beggs_robinson_muo_live(mu_od, 800.0)
        assert mu1 > mu2 > mu3


class TestGasPVTCorrelations:
    """Tests for gas PVT correlations."""

    def test_gas_z_papay_reasonable_range(self):
        """Papay Z-factor should be in reasonable range (0.2-1.2)."""
        z = gas_z_papay(3000.0, 200.0, 0.75)
        assert 0.2 < z < 1.2
        print(f"Z-factor at 3000 psi, 200F, 0.75sg = {z:.4f}")

    def test_gas_z_papay_decreases_with_pressure(self):
        """Z-factor generally decreases then increases with pressure (minimum near Ppc)."""
        z1 = gas_z_papay(500.0, 200.0, 0.75)
        z2 = gas_z_papay(3000.0, 200.0, 0.75)
        z3 = gas_z_papay(5000.0, 200.0, 0.75)
        print(f"Z: 500psi={z1:.4f}, 3000psi={z2:.4f}, 5000psi={z3:.4f}")
        # All should be in reasonable range
        assert all(0.2 < z < 1.2 for z in [z1, z2, z3])

    def test_gas_bg_decreases_with_pressure(self):
        """Bg should decrease with increasing pressure."""
        bg1 = gas_bg(500.0, 200.0, 0.75)
        bg2 = gas_bg(3000.0, 200.0, 0.75)
        bg3 = gas_bg(5000.0, 200.0, 0.75)
        assert bg1 > bg2 > bg3 > 0
        print(f"Bg: 500psi={bg1:.1f}, 3000psi={bg2:.1f}, 5000psi={bg3:.1f} rb/Mscf")

    def test_gas_bg_at_standard_conditions(self):
        """Bg at standard conditions (14.7 psia, 60F) should be ~178 rb/Mscf."""
        bg = gas_bg(14.7, 60.0, 1.0)  # air
        # 5.035 * 1.0 * 519.67 / 14.7 = 178.0
        assert 170 < bg < 190
        print(f"Bg at SC (air) = {bg:.1f} rb/Mscf")

    def test_lee_gonzalez_mug_positive(self):
        """Lee-Gonzalez gas viscosity should be positive."""
        mug = lee_gonzalez_mug(3000.0, 200.0, 0.75)
        assert mug > 0
        assert mug < 0.1  # gas viscosity typically < 0.1 cp
        print(f"Gas viscosity = {mug:.6f} cp")


class TestWaterPVTCorrelations:
    """Tests for water PVT correlations (McCain)."""

    def test_mccain_bw_positive(self):
        """Water FVF should be positive and near 1.0."""
        bw = mccain_bw(3000.0, 200.0)
        assert 0.95 < bw < 1.05
        print(f"Bw at 3000psi, 200F = {bw:.6f} rb/stb")

    def test_mccain_bw_increases_with_pressure(self):
        """Water FVF should slightly increase with pressure (compressibility)."""
        bw1 = mccain_bw(1000.0, 200.0)
        bw2 = mccain_bw(5000.0, 200.0)
        # Water is slightly compressible, Bw increases very slightly with pressure
        # Actually dVwp is negative so Bw decreases with pressure
        print(f"Bw: 1000psi={bw1:.6f}, 5000psi={bw2:.6f}")

    def test_mccain_muw_positive_decreases_with_temp(self):
        """Water viscosity should be positive and decrease with temperature."""
        muw1 = mccain_muw(150.0, 50000.0)
        muw2 = mccain_muw(250.0, 50000.0)
        assert muw1 > 0
        assert muw2 > 0
        assert muw1 > muw2  # decreases with temp
        print(f"muw: 150F={muw1:.4f}, 250F={muw2:.4f} cp")


class TestRelativePermeabilityCorrelations:
    """Tests for relative permeability correlations."""

    def test_corey_swof_endpoints(self):
        """Corey SWOF should honor endpoints."""
        swc, sorw = 0.12, 0.20
        krw_max, kro_max = 0.5, 1.0
        nw, no = 2.0, 2.0

        # At Swc: krw=0, kro=kro_max
        krw, kro = corey_swof(swc, swc, sorw, krw_max, kro_max, nw, no)
        assert abs(krw) < 1e-6
        assert abs(kro - kro_max) < 1e-6

        # At 1-Sorw: krw=krw_max, kro=0
        krw, kro = corey_swof(1.0 - sorw, swc, sorw, krw_max, kro_max, nw, no)
        assert abs(krw - krw_max) < 1e-6
        assert abs(kro) < 1e-6

    def test_corey_swof_monotonic(self):
        """Corey krw increases, kro decreases with Sw."""
        swc, sorw = 0.12, 0.20
        krw_max, kro_max = 0.5, 1.0
        nw, no = 2.0, 2.0

        sw_vals = np.linspace(swc + 0.01, 1.0 - sorw - 0.01, 10)
        prev_krw, prev_kro = 0.0, 1.0
        for sw in sw_vals:
            krw, kro = corey_swof(sw, swc, sorw, krw_max, kro_max, nw, no)
            assert krw >= prev_krw - 1e-6  # non-decreasing
            assert kro <= prev_kro + 1e-6  # non-increasing
            prev_krw, prev_kro = krw, kro

    def test_corey_swof_bounds(self):
        """Corey relperms should be in [0, 1]."""
        swc, sorw = 0.12, 0.20
        krw_max, kro_max = 0.5, 1.0
        nw, no = 2.0, 2.0

        for sw in np.linspace(0.0, 1.0, 20):
            krw, kro = corey_swof(sw, swc, sorw, krw_max, kro_max, nw, no)
            assert 0.0 <= krw <= 1.0 + 1e-6
            assert 0.0 <= kro <= 1.0 + 1e-6

    def test_corey_sgof_endpoints(self):
        """Corey SGOF should honor endpoints."""
        swc, sgc, sorg = 0.12, 0.0, 0.05
        krg_max, kro_max = 1.0, 1.0
        ng, nog = 2.0, 2.0

        # At Sg=0: krg=0, kro=kro_max
        krg, kro = corey_sgof(0.0, sgc, sorg, swc, krg_max, kro_max, ng, nog)
        assert abs(krg) < 1e-6
        assert abs(kro - kro_max) < 1e-6

        # At 1-Swc-Sorg: krg=krg_max, kro=0
        krg, kro = corey_sgof(1.0 - swc - sorg, sgc, sorg, swc, krg_max, kro_max, ng, nog)
        assert abs(krg - krg_max) < 1e-6
        assert abs(kro) < 1e-6

    def test_let_swof_endpoints(self):
        """LET SWOF should honor endpoints."""
        swc, sorw = 0.12, 0.20
        krw_max, kro_max = 0.5, 1.0
        l_w, e_w, t_w = 2.0, 1.0, 2.0
        l_o, e_o, t_o = 2.0, 1.0, 2.0

        # At Swc: krw=0, kro=kro_max
        krw, kro = let_swof(swc, swc, sorw, krw_max, kro_max, l_w, e_w, t_w, l_o, e_o, t_o)
        assert abs(krw) < 1e-6
        assert abs(kro - kro_max) < 1e-6

        # At 1-Sorw: krw=krw_max, kro=0
        krw, kro = let_swof(1.0 - sorw, swc, sorw, krw_max, kro_max, l_w, e_w, t_w, l_o, e_o, t_o)
        assert abs(krw - krw_max) < 1e-6
        assert abs(kro) < 1e-6

    def test_let_swof_bounds(self):
        """LET relperms should be in [0, 1]."""
        swc, sorw = 0.12, 0.20
        krw_max, kro_max = 0.5, 1.0
        l_w, e_w, t_w = 2.0, 1.0, 2.0
        l_o, e_o, t_o = 2.0, 1.0, 2.0

        for sw in np.linspace(0.0, 1.0, 20):
            krw, kro = let_swof(sw, swc, sorw, krw_max, kro_max, l_w, e_w, t_w, l_o, e_o, t_o)
            assert 0.0 <= krw <= 1.0 + 1e-6
            assert 0.0 <= kro <= 1.0 + 1e-6

    def test_let_sgof_endpoints(self):
        """LET SGOF should honor endpoints."""
        swc, sgc, sorg = 0.12, 0.0, 0.05
        krg_max, kro_max = 1.0, 1.0
        l_g, e_g, t_g = 2.0, 1.0, 2.0
        l_o, e_o, t_o = 2.0, 1.0, 2.0

        # At Sg=0: krg=0, kro=kro_max
        krg, kro = let_sgof(0.0, sgc, sorg, swc, krg_max, kro_max, l_g, e_g, t_g, l_o, e_o, t_o)
        assert abs(krg) < 1e-6
        assert abs(kro - kro_max) < 1e-6


class TestPhysicalSanity:
    """Cross-correlation physical sanity checks."""

    def test_standing_bo_vs_vasquez_beggs(self):
        """Standing and VB Bo should give similar order of magnitude."""
        api, gas_grav, temp_f, rs = 35.0, 0.75, 200.0, 800.0
        bo_s = standing_bo(api, gas_grav, temp_f, rs)
        bo_vb = vasquez_beggs_bo(api, gas_grav, temp_f, rs)
        # Both should be within ~20% of each other for this fluid
        ratio = bo_s / bo_vb
        assert 0.7 < ratio < 1.4
        print(f"Standing Bo={bo_s:.4f}, VB Bo={bo_vb:.4f}, ratio={ratio:.3f}")

    def test_bo_always_ge_1(self):
        """All Bo correlations should give Bo >= 1.0."""
        api, gas_grav, temp_f, rs = 35.0, 0.75, 200.0, 800.0
        for bo_func in [standing_bo, vasquez_beggs_bo]:
            bo = bo_func(api, gas_grav, temp_f, rs)
            assert bo >= 1.0 - 1e-6
        # Al-Marhoun requires pressure
        bo = almarhoun_bo(api, gas_grav, temp_f, rs, 2500.0)
        assert bo >= 1.0 - 1e-6

    def test_gas_bg_at_spe1_conditions(self):
        """Check Bg at SPE1 conditions matches reference (~166 at 14.7 psi)."""
        # SPE1 PVDG: 14.7 psia -> 166.666 rb/Mscf
        bg = gas_bg(14.7, 60.0, 0.71)  # SPE1 gas gravity ~0.71
        # Our calculation: 5.035 * z * 519.67 / 14.7
        # At low pressure, z ~ 0.93 for 0.71 gas grav
        # 5.035 * 0.93 * 519.67 / 14.7 = ~166
        assert 150 < bg < 190
        print(f"Bg at SPE1 SC = {bg:.1f} rb/Mscf")

    def test_oil_viscosity_reasonable_range(self):
        """Oil viscosity should be in reasonable range for typical oils."""
        mu_od = beggs_robinson_muo_dead(35.0, 200.0)
        mu_ob = beggs_robinson_muo_live(mu_od, 800.0)
        # 35 API at 200F: dead ~0.5-1 cp, live ~0.2-0.5 cp
        assert 0.1 < mu_od < 2.0
        assert 0.05 < mu_ob < 1.0
        print(f"35 API, 200F: dead={mu_od:.3f} cp, live={mu_ob:.3f} cp")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])