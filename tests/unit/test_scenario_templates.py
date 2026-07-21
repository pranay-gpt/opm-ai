"""Stage D scenario template rendering tests (deck text only, no Flow).

Each of the 5 formerly depletion-like scenarios must render a distinct,
physically sensible deck, and the schedule mechanism must stay invisible
when no schedule events are present.
"""
import re

import pytest

from opm_ai.builder.builder import build_deck, build_deck_from_spec
from opm_ai.builder.extract import extract_parameters_offline
from opm_ai.builder.models import ModelSpec, ScheduleEvent


@pytest.mark.unit
def test_no_schedule_events_renders_no_dates():
    """Empty schedule keeps the pre-Stage-D single-TSTEP deck shape."""
    deck, lint = build_deck("10x10x3 grid, simple depletion, one producer")
    assert lint.passed
    assert "DATES" not in deck
    assert deck.count("TSTEP") == 1


@pytest.mark.unit
def test_schedule_event_dates_and_tstep_render():
    """ScheduleEvent actions render before the DATES/TSTEP advance."""
    spec = ModelSpec()
    spec = extract_parameters_offline("5x5x1 grid, depletion")
    spec.timesteps = [10.0]
    spec.schedule = [
        ScheduleEvent(actions=["WELOPEN\n 'PROD1' 'STOP' /\n/"], date="1 'MAR' 2015"),
        ScheduleEvent(tstep_days=[0.5, 1.0, 2.0]),
    ]
    deck, lint = build_deck_from_spec(spec)
    assert lint.passed
    assert "DATES\n 1 'MAR' 2015 /" in deck
    welopen_pos = deck.index("WELOPEN")
    dates_pos = deck.index("DATES")
    assert welopen_pos < dates_pos
    assert "0.5 \n1 \n2 \n/" in deck


@pytest.mark.unit
def test_wag_deck_alternates_injection_fluid():
    """WAG deck alternates WCONINJE water/gas across half-cycles."""
    deck, lint = build_deck("wag injection on a 15x15x3 grid")
    assert lint.passed
    fluids = re.findall(r"'INJ'\s+(WATER|GAS)\s+OPEN", deck)
    # Initial water half-cycle plus 7 alternating events = 8 half-cycles
    assert len(fluids) == 8
    assert fluids[0] == "WATER"
    for prev, cur in zip(fluids, fluids[1:]):
        assert prev != cur, f"adjacent half-cycles must alternate: {fluids}"
    assert deck.count("DATES") == 7


@pytest.mark.unit
def test_gas_cap_deck_has_goc_and_oil_zone_producer():
    """Gas-cap EQUIL puts the GOC at the top-layer base; producer avoids the cap."""
    deck, lint = build_deck("gas cap reservoir, 10x10x3 grid")
    assert lint.passed
    # EQUIL: datum at GOC 8345 (top 8325 + dz1 20), datum pressure at
    # bubble point, GOC (item 5) = 8345.
    equil_line = deck.split("EQUIL")[1].splitlines()[1]
    items = equil_line.replace("/", "").split()
    assert float(items[0]) == 8345.0   # datum depth
    assert float(items[1]) == 4014.7   # bubble point pressure
    assert float(items[4]) == 8345.0   # GOC depth (item 5)
    # Producer completed in layers 2..3 only (oil zone)
    compdat = deck.split("COMPDAT")[1].split("/")[0]
    assert re.search(r"'PROD'\s+\d+\s+\d+\s+2\s+3\s+OPEN", compdat)


@pytest.mark.unit
def test_co2_deck_has_dense_pvdg_and_gas_injector():
    """CO2 EOR deck swaps in the denser injection-gas PVDG and a gas injector."""
    deck, lint = build_deck("co2 eor flood, 10x10x3 grid")
    assert lint.passed
    assert "145.000" in deck          # CO2-like PVDG first Bg
    assert "166.666" not in deck      # methane-like default replaced
    assert re.search(r"'INJ'\s+GAS\s+OPEN\s+RATE", deck)


@pytest.mark.unit
def test_buildup_deck_stops_producer_then_short_tsteps():
    """Buildup deck flows the producer then stops it with short TSTEPs after."""
    deck, lint = build_deck("pressure buildup test, 10x10x3 grid")
    assert lint.passed
    assert re.search(r"'PROD'\s+STOP\s+ORAT\s+0", deck)
    stop_pos = deck.index("STOP")
    tail = deck[stop_pos:]
    assert "0.25" in tail, "short buildup TSTEPs must follow the shut-in"
    open_pos = deck.index("'PROD' OPEN ORAT")
    assert open_pos < stop_pos, "flow period must precede shut-in"


@pytest.mark.unit
def test_multilayer_deck_has_perm_contrast():
    """Multilayer deck carries the 500/50/200 md per-layer PERMX contrast."""
    deck, lint = build_deck("multilayer reservoir, 12x12x3 grid")
    assert lint.passed
    permx = deck.split("PERMX")[1].split("/")[0]
    layers = [line.split()[0] for line in permx.strip().splitlines()]
    assert layers == ["500.0", "50.0", "200.0"]
    # kv/kh = 0.1 vertical restriction
    permz = deck.split("PERMZ")[1].split("/")[0]
    assert permz.strip().splitlines()[0].split()[0] == "50.0"


@pytest.mark.unit
def test_scenario_decks_are_distinct():
    """The 5 scenario decks must differ from the depletion deck and each other."""
    descs = [
        "10x10x3 grid, simple depletion, one producer",
        "wag injection on a 10x10x3 grid",
        "gas cap reservoir, 10x10x3 grid",
        "co2 eor flood, 10x10x3 grid",
        "pressure buildup test, 10x10x3 grid",
        "multilayer reservoir, 10x10x3 grid",
    ]
    decks = [build_deck(d)[0] for d in descs]
    assert len(set(decks)) == len(decks), "every scenario must render a distinct deck"
