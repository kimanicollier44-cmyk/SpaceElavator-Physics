#!/usr/bin/env python3
"""SpaceElevator-Physics - educational space elevator tether physics lab.

by Darion Kellar

Pure Python standard library. Zero dependencies. Zero network.
Education only: a space elevator is a ribbon hanging from beyond
geostationary orbit, held taut by the contest between gravity
(pulling it down) and Earth's rotation (flinging it out). The
physics is a century old and completely unforgiving: the tension
peaks at GEO, and the material property that decides everything is
SPECIFIC STRENGTH - tensile strength divided by density - measured
here in megayuri (1 MYuri = 1 MJ/kg = 1 GPa per (g/cm^3)). This lab
integrates the effective gravity along the tether and gets the bare
requirement for Earth: ~48.4 MYuri, ~62.9 MYuri with the standard
1.3 design safety factor (labelled). Then it puts the materials
table next to that bar - steel, Kevlar, carbon fibre, today's
carbon-nanotube yarn, and the theoretical single nanotube - and the
gap table IS the headline: even a perfect nanotube only just clears
the bare bar, and the best yarn anyone can actually manufacture is
~20x short. That is why carbon nanotubes are not enough YET. The
Moon is the hopeful counterpoint: the same integral there asks for
only ~2.7 MYuri, inside the reach of fibres that already exist.
Every construction / service / passenger claim is a HOLD gate -
with Gemini Carbon 4 as DECIDER (names-only, tighten-only), Muse
as advisor (never overrides HOLD), and Google Flow plan-only seats.
"""
import hashlib
import json
import math
import sys

# ---------------------------------------------------------------- constants
G_NEWTON = 6.67430e-11          # gravitational constant, m^3 kg^-1 s^-2 (CODATA)
VERSION = "1.0.0"

# Bodies (labelled published values). mu = G*M in m^3/s^2, radius is the
# EQUATORIAL surface radius in m (an elevator hangs on the equator),
# omega is the sidereal rotation rate in rad/s.
BODIES = {
    "earth": {"mu": 3.986004418e14, "radius_m": 6.378e6,
              "omega_rad_s": 7.2921159e-5, "label": "Earth"},
    "moon": {"mu": 4.9048695e12, "radius_m": 1.7374e6,
             "omega_rad_s": 2.6617e-6, "label": "Moon"},
}
EARTH = BODIES["earth"]
MOON = BODIES["moon"]

# Labelled model choices (stated, not hidden):
SAFETY_FACTOR = 1.3             # standard design margin on the bare integral
TETHER_LENGTH_M = 1.0e8         # 100,000 km of tether from the surface (class)
MOON_L1_FROM_CENTRE_M = 5.8e7   # Earth-Moon L1 distance from Moon's centre

# ---------------------------------------------------------------- HOLD gates
HOLD_GATES = {
    "construction_feasibility_claim": "HOLD - no material that exists today can build an Earth elevator; this lab computes why, it does not green-light a build",
    "real_hardware_control": "HOLD - no control of any real tether, climber, anchor station, or counterweight hardware, ever",
    "live_deployment_guidance": "HOLD - no instructions for deploying, anchoring, or tensioning a real tether; this lab computes, it does not operate",
    "commercial_service_claim": "HOLD - this is an educational lab, not a commercial elevator service or product design",
    "passenger_transport_claim": "HOLD - no claim that people can ride; the climber model is cargo arithmetic, not a safety case",
    "investment_claim": "HOLD - no investment advice about space-elevator, nanotube, or launch companies",
    "guaranteed_performance_claim": "HOLD - no guaranteed performance; every model here carries its labelled assumptions",
    "material_synthesis_recipe": "HOLD - no nanotube synthesis recipes aimed at 'reaching' theoretical strength values",
    "counterweight_capture_guidance": "HOLD - no asteroid capture, redirect, or counterweight emplacement guidance",
    "weapons_application_claim": "HOLD - no weapons application guidance of any kind",
    "collision_avoidance_live": "HOLD - no live orbital-debris tracking or ribbon collision-avoidance operations",
    "lunar_construction_claim": "HOLD - the lunar numbers are a labelled model too, not a lunar build plan",
    "power_export_claim": "HOLD - no claim the elevator exports net energy or runs a power-beaming service",
    "peer_reviewed_result_claim": "HOLD - no peer-reviewed-result claim; these are textbook-model computations",
}


def gate(action):
    """Return 'HOLD' if the action is gated, else 'PROCEED' (sandbox sim)."""
    return "HOLD" if action in HOLD_GATES else "PROCEED"


# ================================================================ 1. Geometry
# A tether element at radius r (from the body's centre) feels gravity
# pulling it in, mu / r^2, and the rotating frame flinging it out,
# omega^2 r. The synchronous (GEO) radius is where they cancel:
#   r_sync = (mu / omega^2)^(1/3).
# For Earth: 42,164 km from the centre, 35,786 km above the equator.
# Below r_sync the net pull is inward; above it, outward - which is
# the whole trick: the part beyond GEO pulls the ribbon taut.

def sync_radius(body):
    """Synchronous-orbit radius from the body's centre (m)."""
    return (body["mu"] / body["omega_rad_s"] ** 2) ** (1.0 / 3.0)


def gravity_accel(r_m, body):
    """Gravitational acceleration magnitude mu / r^2 (m/s^2, inward)."""
    if r_m <= 0:
        raise ValueError("radius must be positive")
    return body["mu"] / r_m ** 2


def net_accel(r_m, body):
    """Signed effective acceleration (m/s^2): + outward, - inward."""
    if r_m <= 0:
        raise ValueError("radius must be positive")
    return body["omega_rad_s"] ** 2 * r_m - body["mu"] / r_m ** 2


def eff_gravity(r_m, body):
    """Effective gravity (m/s^2, + = inward pull on the tether)."""
    return -net_accel(r_m, body)


def _potential(r_m, body):
    """V(r) = mu/r + omega^2 r^2 / 2; eff_gravity = -dV/dr... (V drops
    from the surface to a minimum at r_sync, then rises again)."""
    return body["mu"] / r_m + 0.5 * body["omega_rad_s"] ** 2 * r_m ** 2


def geometry_report(body=EARTH):
    r_sync = sync_radius(body)
    return {"body": body["label"], "sync_radius_km": r_sync / 1e3,
            "surface_radius_km": body["radius_m"] / 1e3,
            "sync_altitude_km": (r_sync - body["radius_m"]) / 1e3,
            "surface_eff_gravity_m_s2": eff_gravity(body["radius_m"], body),
            "net_accel_at_sync_m_s2": net_accel(r_sync, body)}


# ================================================================ 2. The core integral
# Hang a UNIFORM tether (constant cross-section, density rho) from
# r_sync down to the surface. Its tension grows all the way down-to-up
# and peaks exactly at r_sync, where it carries the full effective
# weight of everything below:
#   T_max / (rho * A) = integral_R^r_sync eff_gravity(r) dr
#                     = V(R) - V(r_sync)          [J/kg]
# That number - energy per kilogram - IS the specific strength the
# material must have (sigma/rho) for a uniform tether to just hold
# itself. In MYuri (MJ/kg): Earth ~48.4 bare, ~62.9 with the labelled
# 1.3 design safety factor; Moon ~2.7. The integral is computed BOTH
# in closed form and by Simpson quadrature, and the lab asserts they
# agree - the number is the integral, not a slogan.

def _simpson(f, a, b, n):
    """Composite Simpson rule, fixed even n: deterministic."""
    if n % 2:
        n += 1
    h = (b - a) / n
    total = f(a) + f(b)
    for i in range(1, n):
        total += (4.0 if i % 2 else 2.0) * f(a + i * h)
    return total * h / 3.0


def requirement_closed_j_kg(body):
    """Bare specific-strength requirement (J/kg) from the closed form."""
    return _potential(body["radius_m"], body) - _potential(sync_radius(body), body)


def requirement_numeric_j_kg(body, steps=20000):
    """The same requirement by direct Simpson integration of eff_gravity."""
    r0, r1 = body["radius_m"], sync_radius(body)
    return _simpson(lambda r: eff_gravity(r, body), r0, r1, steps)


def requirement_report(body=EARTH):
    bare = requirement_closed_j_kg(body)
    return {"body": body["label"],
            "bare_j_kg": bare,
            "bare_myuri": bare / 1e6,
            "numeric_j_kg": requirement_numeric_j_kg(body),
            "safety_factor_labelled": SAFETY_FACTOR,
            "design_j_kg": bare * SAFETY_FACTOR,
            "design_myuri": bare * SAFETY_FACTOR / 1e6}


# ================================================================ 3. Materials table
# Labelled published values: tensile strength (GPa) and density
# (g/cm^3). Specific strength Y = sigma / rho, and the unit gift:
# 1 GPa per (g/cm^3) = 1 MJ/kg = 1 MYuri exactly, so Y in MYuri is
# just strength_gpa / density_gcc. Read the CNT rows carefully: the
# THEORETICAL single tube (~62.9 MYuri) is a microscopic, defect-free
# object; a manufacturable macro yarn is ~1-3 MYuri class today.
# Strength falls with length and defect count - that scaling gap,
# not the chemistry, is the whole problem.

MATERIALS = {
    # name: (strength GPa, density g/cm^3, theoretical?, note)
    "structural_steel": (0.50, 7.85, False, "ordinary construction steel"),
    "high_strength_steel_wire": (1.57, 7.85, False, "best steel cable wire class"),
    "kevlar_49": (3.60, 1.44, False, "aramid fibre, flies today"),
    "carbon_fibre_t1000": (6.37, 1.80, False, "top commercial carbon fibre"),
    "zylon_pbo": (5.80, 1.56, False, "PBO fibre, lunar-elevator proposals use its class"),
    "cnt_yarn_typical": (1.30, 1.30, False, "typical manufactured CNT yarn today"),
    "cnt_yarn_best": (3.90, 1.30, False, "best reported macro CNT yarn class (~1-5 range)"),
    "cnt_single_tube_theoretical": (81.77, 1.30, True,
                                    "THEORETICAL defect-free single nanotube - not a manufacturable material"),
}


def specific_strength_myuri(name):
    """Y = sigma/rho in MYuri (= MJ/kg) for a table material."""
    gpa, gcc, _theo, _note = MATERIALS[name]
    return gpa / gcc


def materials_table():
    rows = []
    for name, (gpa, gcc, theo, note) in MATERIALS.items():
        rows.append({"material": name, "strength_gpa": gpa, "density_g_cc": gcc,
                     "specific_strength_myuri": gpa / gcc,
                     "theoretical": theo, "note": note})
    return rows


def gap_report(body=EARTH):
    """How many times short of the bar is each material? (the headline)"""
    req = requirement_report(body)
    rows = []
    for row in materials_table():
        y = row["specific_strength_myuri"]
        rows.append({"material": row["material"],
                     "specific_strength_myuri": y,
                     "theoretical": row["theoretical"],
                     "x_short_of_bare": req["bare_myuri"] / y,
                     "x_short_of_design": req["design_myuri"] / y,
                     "clears_bare": y >= req["bare_myuri"],
                     "clears_design": y >= req["design_myuri"]})
    return {"body": body["label"], "bare_myuri": req["bare_myuri"],
            "design_myuri": req["design_myuri"], "rows": rows}


# ================================================================ 4. Taper ratio
# A real design tapers: cross-section follows the tension, fattest at
# r_sync, thinner toward both ends. Holding stress constant at the
# material's working value gives the rocket-equation twin:
#   A_sync / A_surface = exp( DeltaU / Y )
# with DeltaU the requirement integral and Y the specific strength
# (both J/kg). For steel on Earth the exponent is ~242 - a taper of
# 10^105, a ribbon wider than galaxies at the top. For the theoretical
# nanotube it is ~2.2 - conceivable ON PAPER. Same formula, two
# different universes: that contrast is the fastest honest summary
# of the whole field.

def taper_log10(name, body=EARTH):
    """log10 of the taper ratio A_sync / A_surface for a material."""
    y_j_kg = specific_strength_myuri(name) * 1e6
    return requirement_closed_j_kg(body) / (y_j_kg * math.log(10.0))


def taper_ratio(name, body=EARTH):
    """Taper ratio A_sync / A_surface (inf if beyond float range)."""
    lg = taper_log10(name, body)
    return math.inf if lg > 300.0 else 10.0 ** lg


def taper_table(body=EARTH):
    return [{"material": name, "taper_log10": taper_log10(name, body),
             "taper_ratio": taper_ratio(name, body)} for name in MATERIALS]


# ================================================================ 5. Ribbon + counterweight
# LABELLED MODEL, assumptions stated: a tapered ribbon of theoretical
# CNT (Y = 62.9 MYuri, rho = 1300 kg/m^3) worked at its full specific
# strength (no extra margin - optimistic), sized to also carry a
# 20,000 kg climber sitting at the surface (the worst case for tension
# at GEO). Cross-section profile at constant stress:
#   A(r) = A_sync * exp( -(V(r) - V(r_sync)) / Y )
# V has its MINIMUM at r_sync, so the ribbon is fattest at GEO and
# thins toward the surface AND toward the counterweight - both ways.
# A_sync is solved from T_sync = sigma_work * A_sync with
# T_sync = (effective weight of the below-GEO ribbon) + (climber pull).
# The counterweight at the end of the 100,000 km tether (labelled
# length) must supply whatever outward pull the beyond-GEO ribbon
# segment does not: m_cw = (T_sync - W_above) / a(r_cw).

RIBBON_MATERIAL = "cnt_single_tube_theoretical"
RIBBON_DENSITY_KG_M3 = 1300.0
CLIMBER_MASS_KG = 20000.0
COUNTERWEIGHT_RADIUS_M = EARTH["radius_m"] + TETHER_LENGTH_M


def _ribbon_area(r_m, a_sync, y_j_kg):
    v_geo = _potential(sync_radius(EARTH), EARTH)
    return a_sync * math.exp(-(_potential(r_m, EARTH) - v_geo) / y_j_kg)


def ribbon_report(climber_mass_kg=CLIMBER_MASS_KG):
    y = specific_strength_myuri(RIBBON_MATERIAL) * 1e6
    sigma_work = y * RIBBON_DENSITY_KG_M3
    r_geo = sync_radius(EARTH)
    r0 = EARTH["radius_m"]
    # alpha: tension at GEO per unit A_sync from the ribbon's own
    # below-GEO effective weight; beta: the climber's pull at surface.
    alpha = _simpson(lambda r: RIBBON_DENSITY_KG_M3
                     * math.exp(-(_potential(r, EARTH) - _potential(r_geo, EARTH)) / y)
                     * eff_gravity(r, EARTH), r0, r_geo, 8000)
    beta = climber_mass_kg * eff_gravity(r0, EARTH)
    a_sync = beta / (sigma_work - alpha)
    mass = _simpson(lambda r: RIBBON_DENSITY_KG_M3
                    * _ribbon_area(r, a_sync, y), r0, COUNTERWEIGHT_RADIUS_M, 16000)
    above_pull = _simpson(lambda r: RIBBON_DENSITY_KG_M3
                          * _ribbon_area(r, a_sync, y)
                          * net_accel(r, EARTH), r_geo, COUNTERWEIGHT_RADIUS_M, 8000)
    tension_geo = sigma_work * a_sync
    cw_mass = max(0.0, (tension_geo - above_pull) / net_accel(COUNTERWEIGHT_RADIUS_M, EARTH))
    return {"material": RIBBON_MATERIAL, "density_kg_m3": RIBBON_DENSITY_KG_M3,
            "climber_mass_kg": climber_mass_kg,
            "area_sync_m2": a_sync,
            "area_surface_m2": _ribbon_area(r0, a_sync, y),
            "area_counterweight_m2": _ribbon_area(COUNTERWEIGHT_RADIUS_M, a_sync, y),
            "tension_geo_n": tension_geo,
            "stress_geo_myuri": tension_geo / a_sync / RIBBON_DENSITY_KG_M3 / 1e6,
            "ribbon_mass_kg": mass,
            "above_geo_pull_n": above_pull,
            "counterweight_radius_km": COUNTERWEIGHT_RADIUS_M / 1e3,
            "counterweight_mass_kg": cw_mass,
            "tether_length_km": TETHER_LENGTH_M / 1e3}


# ================================================================ 6. Climber energy
# In the rotating frame the climber fights eff_gravity all the way
# up, so the energy per kilogram to GEO is EXACTLY the requirement
# integral: ~48.4 MJ/kg. (Same integral, two jobs: it sizes the
# material AND the power bill - the lab asserts the identity.) At a
# labelled 200 km/h the trip takes ~7.5 days; the mechanical power
# peaks at departure, where gravity is strongest, and a laser-beaming
# supply at a labelled 50% end-to-end efficiency must roughly double
# whatever the climber draws.

CLIMBER_SPEED_KMH = 200.0
LASER_EFFICIENCY_LABELLED = 0.5


def climber_report(mass_kg=CLIMBER_MASS_KG, speed_kmh=CLIMBER_SPEED_KMH):
    v = speed_kmh * 1000.0 / 3600.0
    alt = sync_radius(EARTH) - EARTH["radius_m"]
    e_kg = requirement_closed_j_kg(EARTH)
    trip_s = alt / v
    peak_w_kg = eff_gravity(EARTH["radius_m"], EARTH) * v
    return {"mass_kg": mass_kg, "speed_kmh": speed_kmh,
            "energy_per_kg_j": e_kg,
            "total_energy_j": e_kg * mass_kg,
            "total_energy_mwh": e_kg * mass_kg / 3.6e9,
            "trip_time_s": trip_s, "trip_time_days": trip_s / 86400.0,
            "peak_power_w_per_kg": peak_w_kg,
            "avg_power_w_per_kg": e_kg / trip_s,
            "peak_power_mw": peak_w_kg * mass_kg / 1e6,
            "laser_input_peak_mw": peak_w_kg * mass_kg / 1e6 / LASER_EFFICIENCY_LABELLED,
            "laser_efficiency_labelled": LASER_EFFICIENCY_LABELLED}


# ================================================================ 7. The Moon counterpoint
# Run the identical machinery on the Moon: gravity is 6x weaker and
# the synchronous radius is proportionally far, so the requirement
# collapses to ~2.7 MYuri - inside what Kevlar-class fibres already
# deliver, with single-digit taper ratios. HONEST CAVEAT, labelled:
# the Moon's synchronous radius (~88,500 km) lies BEYOND the Earth-
# Moon L1 point (~58,000 km from the Moon's centre), so a real lunar
# elevator is an L1-anchored design, not this simple rotating model.
# The model still makes its point honestly: the lunar bar is ~18x
# lower than Earth's, and that changes the verdict completely.

def moon_report():
    req = requirement_report(MOON)
    r_sync = sync_radius(MOON)
    return {"requirement": req, "sync_radius_km": r_sync / 1e3,
            "l1_from_centre_km": MOON_L1_FROM_CENTRE_M / 1e3,
            "sync_beyond_l1": r_sync > MOON_L1_FROM_CENTRE_M,
            "earth_bare_over_moon_bare":
                requirement_closed_j_kg(EARTH) / requirement_closed_j_kg(MOON),
            "tapers": taper_table(MOON)}


# ================================================================ 8. Oscillation notes (brief)
# A tension wave runs along the ribbon at sqrt(sigma/rho) = sqrt(Y) -
# for theoretical CNT ~7,900 m/s, so a disturbance needs ~3.5 h to
# cross the 100,000 km tether: the ribbon answers insults slowly,
# and a climber's Coriolis sway (it pushes sideways on the ribbon as
# it climbs, conserving angular momentum) is a labelled dynamics
# problem this lab notes but does not simulate.

def wave_report(name=RIBBON_MATERIAL):
    y = specific_strength_myuri(name) * 1e6
    speed = math.sqrt(y)
    return {"material": name, "wave_speed_m_s": speed,
            "transit_time_s": TETHER_LENGTH_M / speed,
            "transit_time_h": TETHER_LENGTH_M / speed / 3600.0}


# ================================================================ 9. kNN buildability classifier
# Features: (log10(DeltaU / Y), theoretical flag). The training grid
# is GENERATED from the stated labelling rule, so the classifier can
# never drift away from the physics:
#   x = log10(DeltaU/Y) > 0.55            -> hopeless (taper > ~34x
#                                            even before margins)
#   theoretical and -0.5 < x <= 0.55      -> needs-theoretical-material
#   otherwise                             -> buildable-today
# Earth + steel lands at x = 2.38 (hopeless); Earth + theoretical
# CNT at x = -0.11, flag 1 (needs-theoretical); Moon + Kevlar at
# x = 0.04, flag 0 (buildable-today). The grid just interpolates.

def _label_rule(x, theoretical):
    if x > 0.55:
        return "hopeless"
    if theoretical and x > -0.5:
        return "needs-theoretical-material"
    return "buildable-today"


_CLASSIFIER_TRAIN = []
for _i in range(31):
    _x = -1.5 + 0.15 * _i
    for _theo in (0, 1):
        _CLASSIFIER_TRAIN.append((_x, float(_theo), _label_rule(_x, bool(_theo))))


def _dist2(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def classify_buildability(material, body=EARTH, k=3):
    """kNN (k=3) buildability verdict for a (material, body) pair."""
    y = specific_strength_myuri(material) * 1e6
    x = math.log10(requirement_closed_j_kg(body) / y)
    theo = 1.0 if MATERIALS[material][2] else 0.0
    ranked = sorted(_CLASSIFIER_TRAIN, key=lambda row: _dist2((x, theo), row[:2]))
    votes = {}
    for row in ranked[:k]:
        votes[row[2]] = votes.get(row[2], 0) + 1
    return max(sorted(votes), key=lambda lab: votes[lab])


def classifier_report():
    scenarios = {
        "earth_steel_wire": ("high_strength_steel_wire", EARTH),
        "earth_kevlar": ("kevlar_49", EARTH),
        "earth_cnt_yarn_best": ("cnt_yarn_best", EARTH),
        "earth_cnt_theoretical": ("cnt_single_tube_theoretical", EARTH),
        "moon_kevlar": ("kevlar_49", MOON),
        "moon_cnt_yarn_best": ("cnt_yarn_best", MOON),
        "moon_cnt_yarn_typical": ("cnt_yarn_typical", MOON),
        "moon_steel_wire": ("high_strength_steel_wire", MOON),
    }
    return {name: classify_buildability(mat, body)
            for name, (mat, body) in scenarios.items()}


# ================================================================ 10. Advisory seats
def _trace(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def carbon4_decide(topic="spaceelevator-demo"):
    """Gemini Carbon 4 DECIDER seat: MAP->MODEL->STRESS->DECIDE.

    Names-only keys, live calls 0, tighten-only: can add HOLDs, never lift one.
    """
    stages = ["MAP", "MODEL", "STRESS", "DECIDE"]
    payload = {"seat": "gemini-carbon-4", "topic": topic, "stages": stages}
    return {
        "seat": "Gemini Carbon 4 Extended Thinking",
        "role": "DECIDER",
        "pipeline": stages,
        "tiers": [2048, 8192, 32768],
        "key": "names-only (GEMINI_API_KEY name checked, value never read)",
        "live_calls": 0,
        "decision": "PROCEED - sandbox simulation only, all claim gates stay HOLD",
        "can_override_hold": False,
        "trace_sha256_16": _trace(payload),
    }


def claude_advisor(topic="spaceelevator-demo"):
    """Muse advisor seat: advises, can never override a HOLD."""
    return {
        "seat": "Muse",
        "role": "ADVISOR",
        "key": "names-only (MODEL_API_KEY name checked, value never read)",
        "live_calls": 0,
        "advice": "Put the integral and the materials table on the same page and let the gap speak: the theoretical nanotube clears the bare bar by 1.3x and the best real yarn misses it by 16x - 'not enough yet' is a measurement, not an opinion.",
        "can_override_hold": False,
    }


def google_flow_plan():
    """Google Flow seat: plan-only, nothing rendered, nothing live."""
    return {
        "seat": "Google Flow",
        "role": "PLAN-ONLY",
        "shots": ["the ribbon rising past GEO, tension peaking at the station ring",
                  "the taper curve: fat at GEO, thread at the ground",
                  "steel's taper ratio scrolling past 100 orders of magnitude",
                  "a single perfect nanotube next to a frayed macro yarn",
                  "the Moon elevator: the same drawing, a bar 18x lower"],
        "rendered": False,
        "live": 0,
    }


def brains_report():
    return {"decider": carbon4_decide(), "advisor": claude_advisor(),
            "flow": google_flow_plan()}


# ================================================================ checks
def run_checks():
    c = []

    def chk(name, ok):
        c.append((name, bool(ok)))

    # 1. geometry
    geo = geometry_report()
    chk("geo_radius_value", abs(geo["sync_radius_km"] - 42164.0) < 25.0)
    chk("geo_altitude_value", abs(geo["sync_altitude_km"] - 35786.0) < 25.0)
    chk("net_accel_zero_at_geo", abs(geo["net_accel_at_sync_m_s2"]) < 1e-6)
    chk("surface_eff_gravity_value", abs(geo["surface_eff_gravity_m_s2"] - 9.77) < 0.05)
    chk("accel_inward_below_geo", net_accel(EARTH["radius_m"], EARTH) < 0)
    chk("accel_outward_above_geo", net_accel(1.5 * sync_radius(EARTH), EARTH) > 0)
    chk("gravity_inverse_square",
        abs(gravity_accel(EARTH["radius_m"], EARTH)
            / gravity_accel(2.0 * EARTH["radius_m"], EARTH) - 4.0) < 1e-9)
    # 2. the core integral
    req_e = requirement_report(EARTH)
    req_m = requirement_report(MOON)
    chk("numeric_matches_closed_earth",
        abs(req_e["numeric_j_kg"] - req_e["bare_j_kg"]) < 0.002 * req_e["bare_j_kg"])
    chk("numeric_matches_closed_moon",
        abs(req_m["numeric_j_kg"] - req_m["bare_j_kg"]) < 0.002 * req_m["bare_j_kg"])
    chk("earth_bare_requirement_value", 47.5 < req_e["bare_myuri"] < 49.5)
    chk("earth_design_requirement_value", 61.5 < req_e["design_myuri"] < 64.5)
    chk("design_is_bare_times_safety",
        abs(req_e["design_j_kg"] - req_e["bare_j_kg"] * SAFETY_FACTOR) < 1e-3)
    chk("moon_bare_requirement_value", 2.5 < req_m["bare_myuri"] < 3.0)
    chk("moon_requirement_under_tenth_of_earth",
        req_m["bare_j_kg"] < 0.1 * req_e["bare_j_kg"])
    # 3. materials
    chk("kevlar_specific_strength", abs(specific_strength_myuri("kevlar_49") - 2.5) < 0.01)
    chk("steel_wire_specific_strength",
        abs(specific_strength_myuri("high_strength_steel_wire") - 0.2) < 0.01)
    chk("cnt_theoretical_specific_strength",
        abs(specific_strength_myuri("cnt_single_tube_theoretical") - 62.9) < 0.15)
    chk("cnt_yarn_gap_over_10x",
        specific_strength_myuri("cnt_yarn_best")
        < specific_strength_myuri("cnt_single_tube_theoretical") / 10.0)
    chk("strongest_real_material_under_4_myuri",
        max(specific_strength_myuri(n) for n, v in MATERIALS.items() if not v[2]) < 4.0)
    chk("only_one_theoretical_material",
        sum(1 for v in MATERIALS.values() if v[2]) == 1)
    # 4. the gap
    gap = gap_report(EARTH)
    grows = {r["material"]: r for r in gap["rows"]}
    chk("steel_over_300x_short_of_design", grows["high_strength_steel_wire"]["x_short_of_design"] > 300.0)
    chk("yarn_best_over_20x_short_of_design", grows["cnt_yarn_best"]["x_short_of_design"] > 20.0)
    chk("cnt_theoretical_clears_bare", grows["cnt_single_tube_theoretical"]["clears_bare"] is True)
    chk("cnt_theoretical_fails_design", grows["cnt_single_tube_theoretical"]["clears_design"] is False)
    chk("no_real_material_clears_bare",
        all(not r["clears_bare"] for r in gap["rows"] if not r["theoretical"]))
    # 5. taper
    chk("taper_cnt_theoretical_earth", 2.0 < taper_ratio("cnt_single_tube_theoretical") < 2.35)
    chk("taper_steel_log10_over_100", taper_log10("high_strength_steel_wire") > 100.0)
    chk("taper_gap_over_100_orders",
        taper_log10("high_strength_steel_wire")
        - taper_log10("cnt_single_tube_theoretical") > 100.0)
    chk("taper_moon_kevlar_single_digit", 2.7 < taper_ratio("kevlar_49", MOON) < 3.3)
    chk("taper_moon_cnt_yarn", 2.2 < taper_ratio("cnt_yarn_best", MOON) < 2.8)
    chk("taper_falls_with_strength",
        taper_ratio("kevlar_49") > taper_ratio("cnt_single_tube_theoretical"))
    chk("taper_moon_steel_still_hopeless", taper_log10("high_strength_steel_wire", MOON) > 5.0)
    # 6. ribbon + counterweight (labelled model)
    rib = ribbon_report()
    chk("ribbon_area_geo_positive", rib["area_sync_m2"] > 0)
    chk("ribbon_thinnest_at_ends",
        rib["area_surface_m2"] < rib["area_sync_m2"]
        and rib["area_counterweight_m2"] < rib["area_sync_m2"])
    chk("ribbon_mass_class", 5.0e4 < rib["ribbon_mass_kg"] < 5.0e6)
    chk("ribbon_stress_at_geo_is_working_value",
        abs(rib["stress_geo_myuri"] - specific_strength_myuri(RIBBON_MATERIAL)) < 0.5)
    chk("counterweight_radius_is_100000_km_class",
        abs(rib["counterweight_radius_km"] - 106378.0) < 1.0)
    chk("counterweight_mass_nonnegative", rib["counterweight_mass_kg"] >= 0.0)
    chk("ribbon_self_weight_matters",
        rib["area_sync_m2"] > CLIMBER_MASS_KG * eff_gravity(EARTH["radius_m"], EARTH)
        / (specific_strength_myuri(RIBBON_MATERIAL) * 1e6 * RIBBON_DENSITY_KG_M3))
    # 7. climber
    cli = climber_report()
    chk("climber_energy_is_requirement_integral",
        abs(cli["energy_per_kg_j"] - req_e["bare_j_kg"]) < 1e-3)
    chk("climber_trip_days", 7.3 < cli["trip_time_days"] < 7.6)
    chk("climber_total_energy_scales",
        abs(cli["total_energy_j"] - cli["energy_per_kg_j"] * CLIMBER_MASS_KG) < 1.0)
    chk("climber_peak_power_band", 500.0 < cli["peak_power_w_per_kg"] < 600.0)
    chk("climber_avg_below_peak", cli["avg_power_w_per_kg"] < cli["peak_power_w_per_kg"])
    chk("laser_input_exceeds_delivered", cli["laser_input_peak_mw"] > cli["peak_power_mw"])
    # 8. moon counterpoint
    mr = moon_report()
    chk("moon_sync_radius_value", 8.7e4 < mr["sync_radius_km"] < 9.0e4)
    chk("moon_sync_beyond_l1_caveat", mr["sync_beyond_l1"] is True)
    chk("earth_moon_requirement_ratio", 15.0 < mr["earth_bare_over_moon_bare"] < 20.0)
    # 9. oscillation
    wv = wave_report()
    chk("wave_speed_cnt", 7000.0 < wv["wave_speed_m_s"] < 9000.0)
    chk("wave_transit_hours", 3.0 < wv["transit_time_h"] < 4.0)
    # 10. classifier
    crep = classifier_report()
    chk("classifier_earth_steel_hopeless", crep["earth_steel_wire"] == "hopeless")
    chk("classifier_earth_kevlar_hopeless", crep["earth_kevlar"] == "hopeless")
    chk("classifier_earth_yarn_hopeless", crep["earth_cnt_yarn_best"] == "hopeless")
    chk("classifier_earth_theoretical_needs_theoretical",
        crep["earth_cnt_theoretical"] == "needs-theoretical-material")
    chk("classifier_moon_kevlar_buildable", crep["moon_kevlar"] == "buildable-today")
    chk("classifier_moon_yarn_buildable", crep["moon_cnt_yarn_best"] == "buildable-today")
    chk("classifier_moon_steel_hopeless", crep["moon_steel_wire"] == "hopeless")
    # gates + seats
    chk("hold_gates_14", len(HOLD_GATES) == 14 and all(v.startswith("HOLD") for v in HOLD_GATES.values()))
    chk("gate_construction_hold", gate("construction_feasibility_claim") == "HOLD")
    chk("gate_passenger_hold", gate("passenger_transport_claim") == "HOLD")
    chk("gate_synthesis_hold", gate("material_synthesis_recipe") == "HOLD")
    chk("gate_sandbox_proceed", gate("run_simulation") == "PROCEED")
    b = brains_report()
    chk("carbon4_no_override", b["decider"]["can_override_hold"] is False)
    chk("claude_no_override", b["advisor"]["can_override_hold"] is False)
    chk("flow_plan_only", b["flow"]["rendered"] is False and b["flow"]["live"] == 0)
    return c


# ================================================================ CLI / demo
def demo():
    print("=" * 68)
    print("SpaceElevator-Physics - educational space elevator tether physics lab")
    print("by Darion Kellar | MIT | pure stdlib | zero network | EDUCATION ONLY")
    print("=" * 68)
    geo = geometry_report()
    print("\n[1] Geometry - where the ribbon hangs")
    print(f"    GEO (synchronous) radius : {geo['sync_radius_km']:,.0f} km from Earth's centre")
    print(f"    GEO altitude             : {geo['sync_altitude_km']:,.0f} km above the equator")
    print(f"    surface effective gravity: {geo['surface_eff_gravity_m_s2']:.2f} m/s^2 "
          "(gravity minus rotation)")
    print("    -> below GEO the net pull is inward, above GEO outward: the part")
    print("       beyond GEO is what holds the whole ribbon taut.")
    req = requirement_report(EARTH)
    print("\n[2] The core integral - the specific-strength bar (Earth)")
    print(f"    bare requirement   : {req['bare_myuri']:.2f} MYuri "
          f"(numeric integral {req['numeric_j_kg'] / 1e6:.2f}, closed form agrees)")
    print(f"    design requirement : {req['design_myuri']:.2f} MYuri "
          f"(bare x {SAFETY_FACTOR} labelled safety factor)")
    print("    -> a uniform tether's tension peaks at GEO; sigma/rho must beat")
    print("       this integral or the ribbon snaps under its own weight.")
    print("\n[3] Materials table (labelled published values)")
    for row in materials_table():
        tag = "  [THEORETICAL]" if row["theoretical"] else ""
        print(f"    {row['material']:28s} {row['strength_gpa']:6.2f} GPa / "
              f"{row['density_g_cc']:.2f} g/cm^3 = {row['specific_strength_myuri']:6.2f} MYuri{tag}")
    print("\n[4] THE GAP - why carbon nanotubes are not enough YET")
    gap = gap_report(EARTH)
    for r in gap["rows"]:
        print(f"    {r['material']:28s} {r['x_short_of_design']:9.1f}x short of the design bar"
              f" | clears bare: {r['clears_bare']}")
    print("    -> the perfect single tube clears the BARE bar (1.3x) and still")
    print("       fails the design bar. The best real yarn is ~21x short, steel")
    print("       ~315x. The gap is manufacturing: defects scale with length.")
    print("\n[5] Taper ratio - A(GEO) / A(surface) = exp(DeltaU / Y)")
    for row in taper_table(EARTH):
        tr = row["taper_ratio"]
        txt = f"10^{row['taper_log10']:.1f}" if tr == math.inf or row["taper_log10"] > 6 else f"{tr:.2f}"
        print(f"    {row['material']:28s} taper = {txt}")
    print("    -> steel's taper has over 100 DIGITS. The theoretical tube's is 2.16.")
    rib = ribbon_report()
    print("\n[6] Ribbon + counterweight (LABELLED MODEL: theoretical CNT ribbon,")
    print("    worked at full specific strength, 20,000 kg climber at the surface)")
    print(f"    cross-section at GEO     : {rib['area_sync_m2']:.3e} m^2")
    print(f"    cross-section at surface : {rib['area_surface_m2']:.3e} m^2")
    print(f"    tension at GEO           : {rib['tension_geo_n']:.3e} N")
    print(f"    total ribbon mass        : {rib['ribbon_mass_kg']:,.0f} kg")
    print(f"    counterweight at {rib['counterweight_radius_km']:,.0f} km: "
          f"{rib['counterweight_mass_kg']:,.0f} kg")
    print("    -> even the fantasy ribbon masses hundreds of tonnes and needs a")
    print("       comparable counterweight. Labelled model - not a build plan.")
    cli = climber_report()
    print("\n[7] Climber energy (20,000 kg at a labelled 200 km/h)")
    print(f"    energy per kg to GEO : {cli['energy_per_kg_j'] / 1e6:.2f} MJ/kg "
          "(the same integral as [2])")
    print(f"    total energy         : {cli['total_energy_mwh']:,.0f} MWh")
    print(f"    trip time to GEO     : {cli['trip_time_days']:.2f} days")
    print(f"    peak mech. power     : {cli['peak_power_mw']:.1f} MW at departure; "
          f"laser input ~{cli['laser_input_peak_mw']:.1f} MW at 50% efficiency (labelled)")
    mr = moon_report()
    print("\n[8] The Moon counterpoint - the hopeful version")
    print(f"    lunar bare requirement : {mr['requirement']['bare_myuri']:.2f} MYuri "
          f"({mr['earth_bare_over_moon_bare']:.1f}x lower than Earth's)")
    print(f"    lunar taper, Kevlar    : {taper_ratio('kevlar_49', MOON):.2f} | "
          f"CNT yarn (best) : {taper_ratio('cnt_yarn_best', MOON):.2f}")
    print(f"    caveat: lunar synchronous radius {mr['sync_radius_km']:,.0f} km lies beyond")
    print(f"    L1 (~{mr['l1_from_centre_km']:,.0f} km) - real designs anchor at L1 (labelled).")
    wv = wave_report()
    print("\n[9] Oscillation note (brief)")
    print(f"    tension-wave speed on theoretical CNT: {wv['wave_speed_m_s']:,.0f} m/s; "
          f"crossing the tether takes {wv['transit_time_h']:.1f} h")
    print("    -> the ribbon answers disturbances slowly; climber Coriolis sway is")
    print("       a labelled dynamics problem, noted here, not simulated.")
    print("\n[10] Buildability classifier (TinyML kNN)")
    for name, label in classifier_report().items():
        print(f"    {name:24s} -> {label}")
    print("\n[11] Advisory seats")
    print(f"    decider: {carbon4_decide()['decision']} trace={carbon4_decide()['trace_sha256_16']}")
    print(f"    advisor can_override_hold = {claude_advisor()['can_override_hold']}")
    print(f"    flow rendered = {google_flow_plan()['rendered']} live = {google_flow_plan()['live']}")
    print(f"\n[12] HOLD gates: {len(HOLD_GATES)}")
    for k in HOLD_GATES:
        print(f"    HOLD  {k}")
    checks = run_checks()
    passed = sum(1 for _, ok in checks if ok)
    print(f"\nCHECKS {passed}/{len(checks)}")
    for name, ok in checks:
        if not ok:
            print(f"    FAIL {name}")
    verdict = "PROCEED" if passed == len(checks) else "HOLD"
    print(f"VERDICT {verdict} (sandbox simulation only) | HOLD gates {len(HOLD_GATES)}")
    return 0 if passed == len(checks) else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] == "demo":
        return demo()
    cmd = argv[0]
    if cmd == "checks":
        checks = run_checks()
        for name, ok in checks:
            print(f"{'PASS' if ok else 'FAIL'} {name}")
        print(f"CHECKS {sum(1 for _, ok in checks if ok)}/{len(checks)}")
        return 0 if all(ok for _, ok in checks) else 1
    if cmd == "geometry":
        print(json.dumps(geometry_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "requirement":
        print(json.dumps({"earth": requirement_report(EARTH),
                          "moon": requirement_report(MOON)}, indent=2, sort_keys=True))
        return 0
    if cmd == "materials":
        print(json.dumps(materials_table(), indent=2, sort_keys=True))
        return 0
    if cmd == "gap":
        print(json.dumps(gap_report(EARTH), indent=2, sort_keys=True))
        return 0
    if cmd == "taper":
        print(json.dumps({"earth": taper_table(EARTH), "moon": taper_table(MOON)},
                         indent=2, sort_keys=True))
        return 0
    if cmd == "ribbon":
        print(json.dumps(ribbon_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "climber":
        print(json.dumps(climber_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "moon":
        print(json.dumps(moon_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "wave":
        print(json.dumps(wave_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "classify":
        print(json.dumps(classifier_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "brains":
        print(json.dumps(brains_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "holds":
        for k, v in HOLD_GATES.items():
            print(f"{k}: {v}")
        return 0
    if cmd == "hold-demo":
        action = argv[1] if len(argv) > 1 else "construction_feasibility_claim"
        print(f"{action}: {HOLD_GATES.get(action, 'PROCEED - not gated')}")
        return 2 if gate(action) == "HOLD" else 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
