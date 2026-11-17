"""Tests for SpaceElevator-Physics: every number checked against analytics."""
import math

import pytest

import main as m


# ---- geometry
def test_geo_radius_value():
    assert abs(m.sync_radius(m.EARTH) / 1e3 - 42164.0) < 25.0


def test_geo_altitude_value():
    alt = (m.sync_radius(m.EARTH) - m.EARTH["radius_m"]) / 1e3
    assert abs(alt - 35786.0) < 25.0


def test_net_accel_zero_at_geo():
    assert abs(m.net_accel(m.sync_radius(m.EARTH), m.EARTH)) < 1e-6


def test_accel_signs_around_geo():
    r_geo = m.sync_radius(m.EARTH)
    assert m.net_accel(m.EARTH["radius_m"], m.EARTH) < 0
    assert m.net_accel(1.5 * r_geo, m.EARTH) > 0


def test_surface_eff_gravity():
    assert abs(m.eff_gravity(m.EARTH["radius_m"], m.EARTH) - 9.77) < 0.05


def test_gravity_inverse_square():
    r = m.EARTH["radius_m"]
    assert abs(m.gravity_accel(r, m.EARTH) / m.gravity_accel(2 * r, m.EARTH) - 4.0) < 1e-9


def test_invalid_radius_raises():
    with pytest.raises(ValueError):
        m.net_accel(0.0, m.EARTH)
    with pytest.raises(ValueError):
        m.gravity_accel(-1.0, m.EARTH)


# ---- the core integral
def test_numeric_matches_closed_form():
    for body in (m.EARTH, m.MOON):
        num = m.requirement_numeric_j_kg(body)
        closed = m.requirement_closed_j_kg(body)
        assert abs(num - closed) < 0.002 * closed


def test_earth_bare_requirement():
    assert 47.5 < m.requirement_report(m.EARTH)["bare_myuri"] < 49.5


def test_earth_design_requirement():
    rep = m.requirement_report(m.EARTH)
    assert 61.5 < rep["design_myuri"] < 64.5
    assert abs(rep["design_j_kg"] - rep["bare_j_kg"] * 1.3) < 1e-3


def test_moon_requirement_small():
    rep_m = m.requirement_report(m.MOON)
    rep_e = m.requirement_report(m.EARTH)
    assert 2.5 < rep_m["bare_myuri"] < 3.0
    assert rep_m["bare_j_kg"] < 0.1 * rep_e["bare_j_kg"]


# ---- materials
def test_material_specific_strengths():
    assert abs(m.specific_strength_myuri("kevlar_49") - 2.5) < 0.01
    assert abs(m.specific_strength_myuri("high_strength_steel_wire") - 0.2) < 0.01
    assert abs(m.specific_strength_myuri("cnt_single_tube_theoretical") - 62.9) < 0.15


def test_cnt_yarn_vs_tube_gap():
    assert (m.specific_strength_myuri("cnt_yarn_best")
            < m.specific_strength_myuri("cnt_single_tube_theoretical") / 10.0)


def test_no_real_material_clears_earth_bare():
    bare = m.requirement_report(m.EARTH)["bare_myuri"]
    for name, (_g, _d, theo, _n) in m.MATERIALS.items():
        if not theo:
            assert m.specific_strength_myuri(name) < bare


def test_theoretical_tube_clears_bare_fails_design():
    rep = m.requirement_report(m.EARTH)
    y = m.specific_strength_myuri("cnt_single_tube_theoretical")
    assert rep["bare_myuri"] < y < rep["design_myuri"]


def test_gap_factors():
    rows = {r["material"]: r for r in m.gap_report(m.EARTH)["rows"]}
    assert rows["high_strength_steel_wire"]["x_short_of_design"] > 300.0
    assert rows["cnt_yarn_best"]["x_short_of_design"] > 20.0


# ---- taper
def test_taper_cnt_theoretical_earth():
    assert 2.0 < m.taper_ratio("cnt_single_tube_theoretical") < 2.35


def test_taper_steel_astronomical():
    assert m.taper_log10("high_strength_steel_wire") > 100.0
    assert (m.taper_log10("high_strength_steel_wire")
            - m.taper_log10("cnt_single_tube_theoretical")) > 100.0


def test_taper_moon_single_digits():
    assert 2.7 < m.taper_ratio("kevlar_49", m.MOON) < 3.3
    assert 2.2 < m.taper_ratio("cnt_yarn_best", m.MOON) < 2.8


def test_taper_falls_with_strength():
    assert m.taper_ratio("kevlar_49") > m.taper_ratio("cnt_single_tube_theoretical")
    assert m.taper_ratio("kevlar_49", m.MOON) < m.taper_ratio("kevlar_49", m.EARTH)


# ---- ribbon + counterweight (labelled model)
def test_ribbon_profile_fattest_at_geo():
    rib = m.ribbon_report()
    assert rib["area_sync_m2"] > 0
    assert rib["area_surface_m2"] < rib["area_sync_m2"]
    assert rib["area_counterweight_m2"] < rib["area_sync_m2"]


def test_ribbon_mass_and_counterweight():
    rib = m.ribbon_report()
    assert 5.0e4 < rib["ribbon_mass_kg"] < 5.0e6
    assert rib["counterweight_mass_kg"] >= 0.0
    assert abs(rib["counterweight_radius_km"] - 106378.0) < 1.0


def test_ribbon_working_stress():
    rib = m.ribbon_report()
    assert abs(rib["stress_geo_myuri"]
               - m.specific_strength_myuri(m.RIBBON_MATERIAL)) < 0.5


# ---- climber
def test_climber_energy_identity():
    cli = m.climber_report()
    assert abs(cli["energy_per_kg_j"] - m.requirement_closed_j_kg(m.EARTH)) < 1e-3
    assert 47.5e6 < cli["energy_per_kg_j"] < 49.5e6


def test_climber_trip_time():
    assert 7.3 < m.climber_report()["trip_time_days"] < 7.6


def test_climber_power():
    cli = m.climber_report()
    assert 500.0 < cli["peak_power_w_per_kg"] < 600.0
    assert cli["avg_power_w_per_kg"] < cli["peak_power_w_per_kg"]
    assert cli["laser_input_peak_mw"] > cli["peak_power_mw"]


# ---- moon counterpoint
def test_moon_sync_and_l1_caveat():
    mr = m.moon_report()
    assert 8.7e4 < mr["sync_radius_km"] < 9.0e4
    assert mr["sync_beyond_l1"] is True
    assert 15.0 < mr["earth_bare_over_moon_bare"] < 20.0


# ---- oscillation
def test_wave_speed_and_transit():
    wv = m.wave_report()
    assert 7000.0 < wv["wave_speed_m_s"] < 9000.0
    assert 3.0 < wv["transit_time_h"] < 4.0
    assert abs(wv["wave_speed_m_s"]
               - math.sqrt(m.specific_strength_myuri("cnt_single_tube_theoretical") * 1e6)) < 1.0


# ---- classifier
def test_classifier_scenarios():
    rep = m.classifier_report()
    assert rep["earth_steel_wire"] == "hopeless"
    assert rep["earth_kevlar"] == "hopeless"
    assert rep["earth_cnt_yarn_best"] == "hopeless"
    assert rep["earth_cnt_theoretical"] == "needs-theoretical-material"
    assert rep["moon_kevlar"] == "buildable-today"
    assert rep["moon_cnt_yarn_best"] == "buildable-today"
    assert rep["moon_steel_wire"] == "hopeless"


# ---- gates + seats
def test_hold_gates_all_present():
    assert len(m.HOLD_GATES) == 14
    assert all(v.startswith("HOLD") for v in m.HOLD_GATES.values())


def test_claim_gates_hold():
    for action in ("construction_feasibility_claim", "passenger_transport_claim",
                   "material_synthesis_recipe", "commercial_service_claim",
                   "counterweight_capture_guidance", "lunar_construction_claim"):
        assert m.gate(action) == "HOLD"


def test_sandbox_proceeds():
    assert m.gate("run_simulation") == "PROCEED"


def test_seats_never_override():
    b = m.brains_report()
    assert b["decider"]["can_override_hold"] is False
    assert b["advisor"]["can_override_hold"] is False
    assert b["flow"]["rendered"] is False and b["flow"]["live"] == 0


def test_demo_checks_all_pass():
    checks = m.run_checks()
    assert all(ok for _, ok in checks), [n for n, ok in checks if not ok]


def test_demo_deterministic():
    import io
    import contextlib
    out1, out2 = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out1):
        m.demo()
    with contextlib.redirect_stdout(out2):
        m.demo()
    assert out1.getvalue() == out2.getvalue()
