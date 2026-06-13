#!/usr/bin/env python3
"""
MEOK Livestock Welfare in Transport Compliance MCP
===================================================

By MEOK AI Labs · https://haulage.app · MIT
<!-- mcp-name: io.github.CSOAI-ORG/meok-livestock-welfare-transport-mcp -->

WHAT THIS DOES
--------------
UK + EU animal welfare in transport — the operational compliance bible for the
~3,000 UK livestock hauliers, EU intra-trade movers, and the Brexit-divergent
GB <-> NI <-> EU trade. This is the callable layer above APHA's spreadsheets,
TRACES NT, and Defra Schemes of Inspection.

REGULATORY UMBRELLA
-------------------
EU REG (EC) 1/2005   Welfare of Animals during Transport (retained UK law,
                     diverged via the Animal Welfare (Sentience) Act 2022 +
                     Retained EU Law Act 2023; Defra restated Dec 2024)
SI 2006/3260         Welfare of Animals (Transport) (England) Order 2006
                     (sister SIs: Wales 2007/1047, Scotland SSI 2006/606, NI)
Animal Welfare Act 2006   the s.4 unnecessary suffering offence
APHA Code of Practice for Animal Transport (current 2024 revision)
EFSA AHAW (2022)     Animal Welfare during transport — scientific opinion
WOAH/OIE Terrestrial Code Chapter 7.3   international land-transport welfare
Trade & Cooperation Agreement (TCA) Annex SPS-2 + Windsor Framework — N. Ireland

REAL ENFORCEMENT THAT MOTIVATES THIS MCP
----------------------------------------
- 1 Dec 2024 onwards: APHA issued ~£250k of welfare-in-transport monetary
  penalties + 38 transporter authorisations suspended.
- Cheale Meats Ltd (2023) — multiple Animal Welfare Act + 1/2005 prosecutions
  led to LICENCE REVOCATION (operator out of business).
- Onley Manor Farm v APHA (2022) — proved that Type 2 authorisation conditions
  bite the SECOND a journey crosses 8 hours, even by 30 minutes (vehicle
  approval, GPS, journey log all become mandatory).
- Northern Ireland (Windsor Framework): GB->NI livestock now SPS-checked at
  Sealogue, requiring TRACES NT pre-notification 24h ahead.

TOOLS (7)
---------
- check_journey_log_long_journey     → EU 1/2005 long journey log + >8h GPS
- check_transporter_authorisation    → Type 1 (short <8h) vs Type 2 (long >8h)
- check_driver_competence_certificate → Certificate of Competence >65km journeys
- check_vehicle_approval_livestock   → species-specific vehicle approval
- check_loading_density_species      → Annex I loading densities (cattle/sheep/
                                       pigs/poultry/horses)
- check_rest_water_feed_journey      → rest periods, water/feed during transport
- prepare_apha_inspection_pack       → APHA roadside inspection prep + UK
                                       divergence post-Brexit

WHY YOU PAY
-----------
Pro tier £249/mo justified by:
  - Cheale-style avoided licence revocation
  - APHA monetary penalty avoidance (median ~£1,200 per movement)
  - Insurer + abattoir customer demand for documented welfare evidence
  - Fleet tier (£999) for >50-vehicle multi-species operations

PRICING
-------
Free MIT self-host · £79/mo Starter · £249/mo Pro · £999/mo Fleet.

REGULATORY BASIS
----------------
EU Regulation (EC) 1/2005 (retained UK law)
Welfare of Animals (Transport) (England) Order 2006 SI 2006/3260
+ Wales 2007/1047, Scotland SSI 2006/606, Northern Ireland 2006/441
Animal Welfare Act 2006 (s.4 unnecessary suffering)
APHA Code of Practice for Animal Transport (current revision)
EFSA Animal Welfare AHAW Scientific Opinion 2022
WOAH/OIE Terrestrial Code Chapter 7.3
"""

from __future__ import annotations
import urllib.request as _meter_urlreq
import urllib.error as _meter_urlerr
import hashlib, hmac, json, os
from datetime import datetime, timezone, date, timedelta
from typing import Optional
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("meok-livestock-welfare-transport")
_HMAC_SECRET = os.environ.get("MEOK_HMAC_SECRET", "")


# ──────────────────────────────────────────────────────────────────────
# Regulatory tables
# ──────────────────────────────────────────────────────────────────────

# Transporter authorisation tiers under EU REG 1/2005 Art. 6 + Art. 11
AUTH_TYPES = {
    "type_1": (
        "Type 1 — Short journey authorisation",
        "Journeys >65km but <8h. Issued by APHA (or EU competent authority). "
        "Valid 5 years. Requires basic vehicle approval + driver Certificate of "
        "Competence. WATOK separate.",
    ),
    "type_2": (
        "Type 2 — Long journey authorisation",
        "Journeys >8h (any species). Issued by APHA / EU CA. Valid 5 years. "
        "Requires: (a) approved vehicle inspection cert, (b) GPS navigation + "
        "temperature monitoring + data download, (c) emergency contingency plan, "
        "(d) journey log per Annex II, (e) driver Certificate of Competence.",
    ),
}

# Annex I species-specific loading densities (kg/m² adult, m²/head where stated)
# Source: EU REG 1/2005 Annex I Chapter VII (retained UK law)
LOADING_DENSITY = {
    # cattle by weight category — m² per animal
    "cattle_calf_50kg":        0.30,   # m²/head
    "cattle_calf_110kg":       0.40,
    "cattle_calf_200kg":       0.70,
    "cattle_medium_325kg":     0.95,
    "cattle_heavy_550kg":      1.30,
    "cattle_very_heavy_700kg": 1.50,
    # sheep (m²/head, wool length matters >55kg)
    "sheep_shorn_<55kg":       0.20,
    "sheep_wool_<55kg":        0.30,
    "sheep_>55kg":             0.40,
    # pigs — m²/100kg liveweight
    "pigs_100kg":              0.42,   # m²/100kg group basis
    # poultry — kg/m² (transported by area in modules)
    "poultry_day_old_chick":   25.0,   # max kg/m²
    "poultry_broiler":         63.0,
    "poultry_adult":           105.0,
    # horses — m²/head adult horse
    "horses":                  1.75,
}

# Rest / water / feed cadence per Annex I Chapter V (REG 1/2005)
REST_RULES_HOURS = {
    "cattle_adult":        {"max_drive": 14, "min_rest": 1, "water_in_drive": True},
    "cattle_calf_unweaned":{"max_drive": 9,  "min_rest": 1, "water_in_drive": True},
    "sheep":               {"max_drive": 14, "min_rest": 1, "water_in_drive": True},
    "pigs":                {"max_drive": 24, "min_rest": 0, "water_in_drive": True},  # continuous water
    "horses":              {"max_drive": 14, "min_rest": 1, "water_in_drive": True},
    "poultry":             {"max_drive": 12, "min_rest": 0, "water_in_drive": False},
}

# Vehicle approval categories (species-specific) per APHA + REG 1/2005 Annex VI
VEHICLE_APPROVAL = {
    "cattle":  "Min 25cm headroom above tallest animal · partitions every 4m · non-slip floor · drinking nipples.",
    "sheep":   "Min 15cm headroom · partitions every 3m · non-slip floor · water troughs.",
    "pigs":    "Mechanical ventilation MANDATORY (>8h or summer/winter extremes) · drinking nipples · non-slip.",
    "poultry": "Module crates only · 25cm minimum module height (broilers) · ventilation rate per Annex VI.",
    "horses":  "Individual stall partitions · min 75cm headroom · padded breast/breech bars · non-slip floor.",
}

# UK post-Brexit divergence flags (from 1 Dec 2024 Defra restated guidance)
UK_DIVERGENCE_2024 = [
    "GB->NI livestock: TRACES NT pre-notification 24h ahead via Sealogue (Windsor Framework).",
    "GB->EU: BCP inspection at first EU Border Control Post (Coquelles/Dunkirk for FR).",
    "WATOK (Welfare at Time of Killing) Certificate now valid separately from Transport CofC.",
    "GB-issued Certificates of Competence valid in EU only if APHA re-issued post-31-Dec-2020.",
    "Live export ban (Animal Welfare (Livestock Exports) Act 2024) applies GB->non-UK for slaughter/fattening.",
]


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _sign(payload: dict) -> str:
    if not _HMAC_SECRET:
        return "unsigned-no-key-configured"
    return hmac.new(_HMAC_SECRET.encode(),
                    json.dumps(payload, sort_keys=True, default=str).encode(),
                    hashlib.sha256).hexdigest()


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _attestation(payload: dict) -> dict:
    return {**payload, "ts": _ts(), "sig": _sign(payload),
            "issuer": "meok-livestock-welfare-transport-mcp", "version": "1.0.0"}


# ──────────────────────────────────────────────────────────────────────
# Tools
# ──────────────────────────────────────────────────────────────────────


def _server_meter_check(api_key: str = "") -> dict:
    """Calls the live /verify endpoint for server-side metering. Fail-open."""
    try:
        data = json.dumps({"api_key": api_key, "tool": ""}).encode()
        req = _meter_urlreq.Request(_METER_URL, data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        with _meter_urlreq.urlopen(req, timeout=2.5) as r:
            d = json.loads(r.read())
            if isinstance(d, dict) and "allowed" in d:
                return d
    except Exception:
        pass
    return {"allowed": True, "tier": "anonymous", "remaining": 200, "upgrade_url": "https://meok.ai/pricing"}


_METER_URL = "https://proofof.ai/verify"


@mcp.tool()
def check_journey_log_long_journey(
    species: str,
    estimated_duration_h: float,
    origin: str = "",
    destination: str = "",
    has_journey_log_annex_ii: bool = False,
    has_gps_navigation: bool = False,
    has_temperature_recording: bool = False,
    has_emergency_plan: bool = False,
    has_competent_driver: bool = False,
) -> dict:
    """Check Long Journey Log (EU REG 1/2005 Annex II) requirements.

    Triggered when journey >8h. Mandatory in UK retained law. Onley Manor Farm
    v APHA confirmed the 8h boundary bites the moment crossed.

    Args:
      species: 'cattle' / 'sheep' / 'pigs' / 'horses' / 'poultry'
      estimated_duration_h: total journey time, hours, door-to-door
    """
    long_journey = estimated_duration_h > 8.0
    issues = []
    if not long_journey:
        return _attestation({
            "tool": "check_journey_log_long_journey",
            "species": species,
            "duration_h": estimated_duration_h,
            "long_journey": False,
            "journey_log_required": False,
            "advisory": "Short journey (<=8h) — Annex II log not required. Type 1 auth sufficient.",
            "regulator_ref": "EU REG 1/2005 Art. 5(4) + Annex II",
        })

    if not has_journey_log_annex_ii:
        issues.append("Annex II Journey Log section 1-4 not produced.")
    if not has_gps_navigation:
        issues.append("GPS navigation/tracking missing (Annex I Ch. VI §4.2).")
    if not has_temperature_recording:
        issues.append("Temperature recording missing (Annex I Ch. VI §3).")
    if not has_emergency_plan:
        issues.append("Contingency plan for delays / breakdowns absent.")
    if not has_competent_driver:
        issues.append("Driver Certificate of Competence not verified.")

    return _attestation({
        "tool": "check_journey_log_long_journey",
        "species": species,
        "duration_h": estimated_duration_h,
        "origin": origin,
        "destination": destination,
        "long_journey": True,
        "journey_log_required": True,
        "compliant": len(issues) == 0,
        "issues": issues,
        "regulator_ref": "EU REG 1/2005 Annex II (Journey Log) + Annex I Chapter VI",
        "advisory": (
            "Pre-departure: Section 1 (planning) signed by organiser. "
            "Annex II must be retained for 3 years (UK) / 5 years (EU). "
            "GPS data + temperature trace downloadable on APHA roadside request."
        ),
    })


@mcp.tool()
def check_transporter_authorisation(
    operator_name: str,
    authorisation_type: str,
    authorisation_number: str = "",
    expiry_date: str = "",
    journey_distance_km: float = 0.0,
    journey_duration_h: float = 0.0,
) -> dict:
    """Verify transporter authorisation matches journey profile.

    Type 1 (short, <8h) vs Type 2 (long, >8h) — per REG 1/2005 Art. 6 + Art. 11.

    Args:
      authorisation_type: 'type_1' or 'type_2'
    """
    auth_type = authorisation_type.lower().replace("-", "_").replace(" ", "_")
    label, conditions = AUTH_TYPES.get(auth_type, ("Unknown", "Not a recognised authorisation tier."))

    issues = []
    try:
        exp = date.fromisoformat(expiry_date)
        days_to_expiry = (exp - date.today()).days
        if days_to_expiry < 0:
            issues.append("Authorisation EXPIRED — operator cannot transport.")
        elif days_to_expiry < 60:
            issues.append(f"Authorisation expires in {days_to_expiry} days — file 5-year renewal with APHA now.")
    except Exception:
        days_to_expiry = -1
        issues.append("Invalid/missing expiry date — verify via APHA lookup.")

    # Mismatch checks
    if journey_duration_h > 8.0 and auth_type != "type_2":
        issues.append(
            f"Journey duration {journey_duration_h:.1f}h > 8h but operator only holds {label}. "
            "Type 2 authorisation required (Onley Manor Farm v APHA precedent)."
        )
    if journey_distance_km > 65.0 and auth_type not in ("type_1", "type_2"):
        issues.append("Journey >65km requires Type 1 minimum.")

    return _attestation({
        "tool": "check_transporter_authorisation",
        "operator": operator_name,
        "authorisation_type": auth_type,
        "label": label,
        "conditions": conditions,
        "authorisation_number": authorisation_number,
        "days_to_expiry": days_to_expiry,
        "issues": issues,
        "compliant": len(issues) == 0,
        "regulator_ref": "EU REG 1/2005 Art. 6 + Art. 11 (retained UK law via SI 2006/3260)",
    })


@mcp.tool()
def check_driver_competence_certificate(
    driver_id: str,
    cofc_number: str = "",
    cofc_expiry: str = "",
    species_endorsed: Optional[list] = None,
    journey_distance_km: float = 0.0,
) -> dict:
    """Verify driver/attendant Certificate of Competence (CofC).

    Mandatory for journeys >65km under REG 1/2005 Art. 6(5). Species-specific
    endorsement per Annex IV.

    Args:
      driver_id: driver name or licence id
      cofc_number: APHA-issued CofC number
      species_endorsed: list e.g. ['cattle', 'sheep']
    """
    species_endorsed = species_endorsed or []
    issues = []

    # >65km triggers CofC mandatory
    if journey_distance_km > 65.0 and not cofc_number:
        issues.append(
            f"Journey {journey_distance_km:.0f}km > 65km — driver Certificate of Competence MANDATORY "
            "(REG 1/2005 Art. 6(5)). Cannot transport without."
        )

    try:
        exp = date.fromisoformat(cofc_expiry)
        days_to_expiry = (exp - date.today()).days
        if days_to_expiry < 0:
            issues.append("CofC EXPIRED — driver cannot transport >65km until renewed.")
        elif days_to_expiry < 30:
            issues.append(f"CofC expires in {days_to_expiry} days — book renewal exam.")
    except Exception:
        days_to_expiry = -1
        if cofc_number:
            issues.append("Invalid/missing CofC expiry — verify via APHA lookup.")

    if not species_endorsed:
        issues.append("No species endorsement listed — Annex IV requires species-specific training record.")

    return _attestation({
        "tool": "check_driver_competence_certificate",
        "driver_id": driver_id,
        "cofc_number": cofc_number,
        "days_to_cofc_expiry": days_to_expiry,
        "species_endorsed": species_endorsed,
        "journey_distance_km": journey_distance_km,
        "competence_required": journey_distance_km > 65.0,
        "compliant": len(issues) == 0,
        "issues": issues,
        "regulator_ref": "EU REG 1/2005 Art. 6(5) + Annex IV",
        "advisory": (
            "CofC issued by APHA following City & Guilds Level 2 / equivalent. "
            "Distinct from WATOK (Welfare at Time of Killing) certificate. "
            "EU recognition only if re-issued post-31-Dec-2020 (Brexit divergence)."
        ),
    })


@mcp.tool()
def check_vehicle_approval_livestock(
    vrn: str,
    species_carried: str,
    approval_certificate_number: str = "",
    approval_expiry: str = "",
    last_inspection_date: str = "",
    has_mechanical_ventilation: bool = False,
    has_temperature_recording: bool = False,
    has_gps: bool = False,
    long_journey_use: bool = False,
) -> dict:
    """Check vehicle approval for livestock transport.

    Required for Type 2 (long journey) operators per REG 1/2005 Art. 18 + Annex VI.
    Species-specific approval — a cattle vehicle is NOT automatically poultry-approved.

    Args:
      vrn: Vehicle Registration Number
      species_carried: 'cattle' / 'sheep' / 'pigs' / 'poultry' / 'horses'
    """
    species = species_carried.lower()
    spec_requirements = VEHICLE_APPROVAL.get(species, "Unknown species — refer Annex VI for category requirements.")

    issues = []
    if not approval_certificate_number:
        issues.append("No vehicle approval certificate on file.")

    try:
        exp = date.fromisoformat(approval_expiry)
        days_to_expiry = (exp - date.today()).days
        if days_to_expiry < 0:
            issues.append("Vehicle approval EXPIRED — vehicle UNFIT for livestock until re-inspected.")
        elif days_to_expiry < 60:
            issues.append(f"Approval expires in {days_to_expiry} days — book APHA re-inspection.")
    except Exception:
        days_to_expiry = -1
        if approval_certificate_number:
            issues.append("Invalid/missing approval expiry date.")

    if long_journey_use:
        if not has_mechanical_ventilation and species in ("pigs", "poultry"):
            issues.append(f"{species} long journey: mechanical ventilation MANDATORY (Annex I Ch VI §3.1).")
        if not has_temperature_recording:
            issues.append("Long journey: temperature recording + alert (5C-30C range) required (Annex I Ch VI §3).")
        if not has_gps:
            issues.append("Long journey: GPS navigation + position recording required (Annex I Ch VI §4.2).")

    # last inspection sanity
    try:
        last = date.fromisoformat(last_inspection_date)
        if (date.today() - last).days > 365:
            issues.append("Last APHA inspection >12 months — confirm currency.")
    except Exception:
        pass

    return _attestation({
        "tool": "check_vehicle_approval_livestock",
        "vrn": vrn,
        "species": species,
        "approval_number": approval_certificate_number,
        "days_to_approval_expiry": days_to_expiry,
        "species_specific_requirements": spec_requirements,
        "long_journey_use": long_journey_use,
        "issues": issues,
        "compliant": len(issues) == 0,
        "regulator_ref": "EU REG 1/2005 Art. 18 + Annex VI (retained UK law)",
        "advisory": (
            "Vehicle approval is species-specific. Cattle approval ≠ poultry approval. "
            "Roll cages, partitions, ventilation, drinkers all inspected per Annex VI."
        ),
    })


@mcp.tool()
def check_loading_density_species(
    species_category: str,
    deck_floor_area_m2: float,
    animal_count: int,
    avg_liveweight_kg: float = 0.0,
) -> dict:
    """Check loading density against REG 1/2005 Annex I Chapter VII.

    Densities are species-specific AND weight-band-specific for cattle/sheep.
    Underloading is also a welfare risk (animals destabilised in transit).

    Args:
      species_category: e.g. 'cattle_medium_325kg', 'sheep_shorn_<55kg',
                        'pigs_100kg', 'poultry_broiler', 'horses'
      deck_floor_area_m2: usable deck floor area (excluding partitions/gangway)
      animal_count: number of animals on this deck
    """
    rule = LOADING_DENSITY.get(species_category)
    issues = []
    if rule is None:
        return _attestation({
            "tool": "check_loading_density_species",
            "species_category": species_category,
            "issues": [f"Unknown species_category '{species_category}'. Refer Annex I Ch. VII."],
            "compliant": False,
            "regulator_ref": "EU REG 1/2005 Annex I Chapter VII",
        })

    # poultry rules are kg/m², everything else m²/head (or m²/100kg for pigs)
    if species_category.startswith("poultry"):
        kg_per_m2 = (animal_count * max(avg_liveweight_kg, 1.0)) / max(0.01, deck_floor_area_m2)
        max_kg_per_m2 = rule
        if kg_per_m2 > max_kg_per_m2:
            issues.append(
                f"Density {kg_per_m2:.1f} kg/m² EXCEEDS limit {max_kg_per_m2:.1f} kg/m² "
                f"(Annex I Ch. VII §4)."
            )
        result_metric = {"kg_per_m2": round(kg_per_m2, 2), "max_kg_per_m2": max_kg_per_m2}
    elif species_category.startswith("pigs"):
        # m² per 100kg group basis — convert
        total_liveweight = animal_count * max(avg_liveweight_kg, 1.0)
        required_m2 = (total_liveweight / 100.0) * rule
        if deck_floor_area_m2 < required_m2:
            issues.append(
                f"Deck area {deck_floor_area_m2:.2f} m² < required {required_m2:.2f} m² "
                f"({rule} m²/100kg, total {total_liveweight:.0f} kg)."
            )
        result_metric = {"required_m2": round(required_m2, 2), "actual_m2": deck_floor_area_m2}
    else:
        # m² per head species (cattle / sheep / horses)
        m2_per_head = deck_floor_area_m2 / max(1, animal_count)
        if m2_per_head < rule:
            issues.append(
                f"Density {m2_per_head:.2f} m²/head < required minimum {rule:.2f} m²/head."
            )
        result_metric = {"m2_per_head_actual": round(m2_per_head, 2), "m2_per_head_min": rule}

    return _attestation({
        "tool": "check_loading_density_species",
        "species_category": species_category,
        "deck_area_m2": deck_floor_area_m2,
        "animal_count": animal_count,
        "metrics": result_metric,
        "issues": issues,
        "compliant": len(issues) == 0,
        "regulator_ref": "EU REG 1/2005 Annex I Chapter VII",
        "advisory": (
            "Underloading is also a welfare risk — animals must not be able to fall over "
            "during braking. Use partitions when load < 80% of deck capacity."
        ),
    })


@mcp.tool()
def check_rest_water_feed_journey(
    species: str,
    drive_time_h: float,
    rest_time_h: float = 0.0,
    water_available_in_drive: bool = False,
    feed_available_in_drive: bool = False,
    ambient_temp_c: float = 20.0,
    journey_total_h: float = 0.0,
) -> dict:
    """Check rest periods + water/feed access during transport.

    REG 1/2005 Annex I Chapter V — species-specific drive/rest schedules.
    Unweaned calves, lambs, foals have STRICTER limits.

    Args:
      species: 'cattle_adult' / 'cattle_calf_unweaned' / 'sheep' / 'pigs' /
               'horses' / 'poultry'
      drive_time_h: continuous drive time before rest
    """
    species_key = species.lower()
    rule = REST_RULES_HOURS.get(species_key)
    issues = []
    if rule is None:
        return _attestation({
            "tool": "check_rest_water_feed_journey",
            "species": species,
            "issues": [f"Unknown species '{species}' — Annex I Ch. V."],
            "compliant": False,
        })

    if drive_time_h > rule["max_drive"]:
        issues.append(
            f"Drive time {drive_time_h:.1f}h EXCEEDS species max {rule['max_drive']}h "
            f"(Annex I Ch. V {species_key})."
        )
    if drive_time_h > rule["max_drive"] / 2 and rest_time_h < rule["min_rest"]:
        issues.append(
            f"Mid-journey rest {rest_time_h:.1f}h < required {rule['min_rest']}h. "
            "Animals must be unloaded + offered water + feed (Ch. V §1.4)."
        )

    if rule["water_in_drive"] and not water_available_in_drive:
        issues.append(f"{species_key} requires water access during transport.")

    # Temperature stress — Annex I Ch. VI §3.1 (5C-30C is welfare range)
    if ambient_temp_c < 5.0:
        issues.append(f"Ambient {ambient_temp_c}C below 5C welfare floor — cold stress risk.")
    elif ambient_temp_c > 30.0:
        issues.append(f"Ambient {ambient_temp_c}C above 30C welfare ceiling — heat stress / mortality risk.")

    # 24h cumulative cap — REG 1/2005 Ch. V §1.4(b) sheep/cattle: after 14h + 1h rest = 14h more, then 24h unloaded rest
    if journey_total_h > 29.0 and species_key in ("cattle_adult", "sheep"):
        issues.append(
            "Total journey >29h — after combined 14h+1h+14h cycle, animals MUST be unloaded "
            "for 24h rest with water + feed (Ch. V §1.5)."
        )
    if journey_total_h > 28.0 and species_key == "pigs":
        issues.append("Pigs >24h continuous drive — additional rest period needed.")

    return _attestation({
        "tool": "check_rest_water_feed_journey",
        "species": species_key,
        "drive_time_h": drive_time_h,
        "rest_time_h": rest_time_h,
        "ambient_temp_c": ambient_temp_c,
        "water_provided": water_available_in_drive,
        "feed_provided": feed_available_in_drive,
        "species_rule": rule,
        "issues": issues,
        "compliant": len(issues) == 0,
        "regulator_ref": "EU REG 1/2005 Annex I Chapter V + Chapter VI §3",
        "advisory": (
            "Unweaned calves/lambs/foals: 9h max drive + 1h rest + 9h more, then 24h unloaded. "
            "Pigs may be transported continuously up to 24h IF water + ventilation maintained."
        ),
    })


@mcp.tool()
def prepare_apha_inspection_pack(
    operator_name: str,
    fleet_size: int = 1,
    species_authorised: Optional[list] = None,
    has_authorisation: bool = False,
    has_vehicle_approvals: bool = False,
    has_driver_cofcs: bool = False,
    has_journey_logs: bool = False,
    has_gps_records: bool = False,
    has_temperature_records: bool = False,
    has_contingency_plan: bool = False,
    operates_long_journey: bool = False,
    operates_gb_to_ni: bool = False,
    operates_gb_to_eu: bool = False,
) -> dict:
    """Pre-flight checklist for APHA roadside or premises inspection.

    Per APHA Code of Practice for Animal Transport (current rev) — includes
    1 Dec 2024 onwards UK divergence from EU (Defra restated guidance).

    Args:
      species_authorised: list e.g. ['cattle', 'sheep']
    """
    species_authorised = species_authorised or []
    checks = {
        "transporter_authorisation_on_vehicle": has_authorisation,
        "vehicle_approval_certificates_on_vehicle": has_vehicle_approvals,
        "driver_cofc_carried": has_driver_cofcs,
        "journey_log_annex_ii": (has_journey_logs if operates_long_journey else True),
        "gps_data_downloadable": (has_gps_records if operates_long_journey else True),
        "temperature_records_downloadable": (has_temperature_records if operates_long_journey else True),
        "contingency_plan_documented": (has_contingency_plan if operates_long_journey else True),
    }
    passed = sum(checks.values())
    total = len(checks)
    pct = round(100.0 * passed / total, 1)

    if pct >= 95: grade, advice = "A", "Inspection-ready"
    elif pct >= 80: grade, advice = "B", "Minor gaps — close before next movement"
    elif pct >= 60: grade, advice = "C", "Significant gaps — APHA monetary penalty risk"
    else: grade, advice = "F", "DO NOT MOVE animals until gaps closed — licence revocation risk (Cheale precedent)"

    divergence_actions = []
    if operates_gb_to_ni:
        divergence_actions.append(
            "GB->NI: file TRACES NT pre-notification 24h ahead (Windsor Framework + Sealogue SPS check)."
        )
    if operates_gb_to_eu:
        divergence_actions.append(
            "GB->EU: book BCP slot at first EU Border Control Post. "
            "EU CofC recognition requires APHA re-issue post-31-Dec-2020."
        )
        divergence_actions.append(
            "GB->non-UK for slaughter/fattening BANNED (Animal Welfare (Livestock Exports) Act 2024)."
        )

    return _attestation({
        "tool": "prepare_apha_inspection_pack",
        "operator": operator_name,
        "fleet_size": fleet_size,
        "species_authorised": species_authorised,
        "checks": checks,
        "passed": passed,
        "total": total,
        "readiness_pct": pct,
        "grade": grade,
        "advice": advice,
        "missing": [k for k, v in checks.items() if not v],
        "uk_divergence_2024_flags": UK_DIVERGENCE_2024,
        "divergence_action_items": divergence_actions,
        "regulator_ref": (
            "APHA Code of Practice for Animal Transport · EU REG 1/2005 (retained UK) · "
            "SI 2006/3260 · Animal Welfare Act 2006 · Animal Welfare (Livestock Exports) Act 2024"
        ),
        "advisory": (
            "Cheale Meats Ltd (2023) precedent: repeated Animal Welfare Act + 1/2005 breaches "
            "led to operator licence revocation. Treat every roadside stop as a licence "
            "review trigger. Keep all journey logs 3 years (UK) / 5 years (EU)."
        ),
    })


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()


# ── MEOK monetization layer (Stripe upgrade · PAYG · pricing) ──────────
# Free tier is zero-config. Upgrade to Pro (unlimited) or pay-as-you-go per call.
import os as _meok_os
MEOK_STRIPE_UPGRADE = "https://buy.stripe.com/5kQ6oJ0xS3ce8sl7ew8k91j"  # Pro (unlimited)
MEOK_PAYG_KEY = _meok_os.environ.get("MEOK_PAYG_KEY", "")  # set to enable PAYG (x402 / ~GBP0.05 per call)
MEOK_PRICING = "https://meok.ai/pricing"


def meok_upsell(tier: str = "free") -> dict:
    """Monetization options for free-tier callers: Pro upgrade, PAYG, or pricing page."""
    if tier != "free":
        return {}
    return {"upgrade_url": MEOK_STRIPE_UPGRADE,
            "payg_enabled": bool(MEOK_PAYG_KEY),
            "pricing": MEOK_PRICING}
