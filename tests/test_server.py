"""Smoke tests for meok-livestock-welfare-transport-mcp."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta

from server import (
    check_journey_log_long_journey,
    check_transporter_authorisation,
    check_driver_competence_certificate,
    check_vehicle_approval_livestock,
    check_loading_density_species,
    check_rest_water_feed_journey,
    prepare_apha_inspection_pack,
    AUTH_TYPES, LOADING_DENSITY, REST_RULES_HOURS, VEHICLE_APPROVAL,
    UK_DIVERGENCE_2024,
)


def _call(t, **kw):
    fn = t.fn if hasattr(t, "fn") else t
    return fn(**kw)


def _future(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


# ─── 1. check_journey_log_long_journey ──────────────────────────────

def test_short_journey_no_log_required():
    r = _call(check_journey_log_long_journey, species="cattle",
              estimated_duration_h=4.0)
    assert r["long_journey"] is False
    assert r["journey_log_required"] is False


def test_long_journey_all_missing_flagged():
    r = _call(check_journey_log_long_journey, species="sheep",
              estimated_duration_h=12.0)
    assert r["long_journey"] is True
    assert r["journey_log_required"] is True
    assert r["compliant"] is False
    assert any("Annex II" in i for i in r["issues"])
    assert any("GPS" in i for i in r["issues"])


def test_long_journey_fully_compliant():
    r = _call(check_journey_log_long_journey, species="cattle",
              estimated_duration_h=10.0,
              has_journey_log_annex_ii=True, has_gps_navigation=True,
              has_temperature_recording=True, has_emergency_plan=True,
              has_competent_driver=True)
    assert r["compliant"] is True


# ─── 2. check_transporter_authorisation ──────────────────────────────

def test_type_2_required_for_long_journey():
    r = _call(check_transporter_authorisation,
              operator_name="Test Hauliers Ltd",
              authorisation_type="type_1",
              authorisation_number="TR-123",
              expiry_date=_future(400),
              journey_distance_km=300, journey_duration_h=10.0)
    assert r["compliant"] is False
    assert any("Type 2" in i for i in r["issues"])


def test_type_1_ok_for_short_journey():
    r = _call(check_transporter_authorisation,
              operator_name="Short Hop Ltd",
              authorisation_type="type_1",
              authorisation_number="TR-456",
              expiry_date=_future(400),
              journey_distance_km=80, journey_duration_h=4.0)
    assert r["compliant"] is True


def test_expired_authorisation_flagged():
    r = _call(check_transporter_authorisation,
              operator_name="Stale Ltd",
              authorisation_type="type_2",
              authorisation_number="TR-OLD",
              expiry_date="2020-01-01",
              journey_distance_km=500, journey_duration_h=12.0)
    assert any("EXPIRED" in i for i in r["issues"])


# ─── 3. check_driver_competence_certificate ──────────────────────────

def test_cofc_required_above_65km():
    r = _call(check_driver_competence_certificate,
              driver_id="DRV-001",
              cofc_number="",
              journey_distance_km=100)
    assert r["compliant"] is False
    assert any("MANDATORY" in i for i in r["issues"])


def test_cofc_valid_with_species():
    r = _call(check_driver_competence_certificate,
              driver_id="DRV-002",
              cofc_number="COFC-9988",
              cofc_expiry=_future(400),
              species_endorsed=["cattle", "sheep"],
              journey_distance_km=200)
    assert r["compliant"] is True


def test_cofc_expired_flagged():
    r = _call(check_driver_competence_certificate,
              driver_id="DRV-003",
              cofc_number="COFC-OLD",
              cofc_expiry="2019-01-01",
              species_endorsed=["cattle"],
              journey_distance_km=100)
    assert any("EXPIRED" in i for i in r["issues"])


# ─── 4. check_vehicle_approval_livestock ─────────────────────────────

def test_pigs_long_journey_need_mechanical_ventilation():
    r = _call(check_vehicle_approval_livestock,
              vrn="AB12 CDE", species_carried="pigs",
              approval_certificate_number="APP-1",
              approval_expiry=_future(200),
              last_inspection_date=_future(-100),
              long_journey_use=True)
    assert any("mechanical ventilation" in i.lower() for i in r["issues"])


def test_vehicle_approval_expired():
    r = _call(check_vehicle_approval_livestock,
              vrn="XY99 ZAB", species_carried="cattle",
              approval_certificate_number="APP-OLD",
              approval_expiry="2020-01-01",
              last_inspection_date="2019-01-01")
    assert any("EXPIRED" in i for i in r["issues"])


def test_cattle_short_journey_compliant():
    r = _call(check_vehicle_approval_livestock,
              vrn="CD34 EFG", species_carried="cattle",
              approval_certificate_number="APP-2",
              approval_expiry=_future(200),
              last_inspection_date=_future(-100),
              long_journey_use=False)
    assert r["compliant"] is True


# ─── 5. check_loading_density_species ────────────────────────────────

def test_cattle_density_too_tight_flagged():
    # 10 medium cattle (325kg) need >= 9.5 m² total. Give 6 m².
    r = _call(check_loading_density_species,
              species_category="cattle_medium_325kg",
              deck_floor_area_m2=6.0, animal_count=10)
    assert r["compliant"] is False


def test_cattle_density_compliant():
    # 10 medium cattle, 12 m² deck
    r = _call(check_loading_density_species,
              species_category="cattle_medium_325kg",
              deck_floor_area_m2=12.0, animal_count=10)
    assert r["compliant"] is True


def test_poultry_density_too_high_kg_per_m2():
    # broiler limit 63 kg/m². 200 broilers x 2kg = 400kg on 5 m² = 80 kg/m²
    r = _call(check_loading_density_species,
              species_category="poultry_broiler",
              deck_floor_area_m2=5.0, animal_count=200,
              avg_liveweight_kg=2.0)
    assert r["compliant"] is False


def test_unknown_species_category_flagged():
    r = _call(check_loading_density_species,
              species_category="alpaca_xl",
              deck_floor_area_m2=20.0, animal_count=5)
    assert r["compliant"] is False


# ─── 6. check_rest_water_feed_journey ────────────────────────────────

def test_cattle_drive_too_long_flagged():
    r = _call(check_rest_water_feed_journey,
              species="cattle_adult", drive_time_h=16.0,
              water_available_in_drive=True, ambient_temp_c=15)
    assert r["compliant"] is False
    assert any("EXCEEDS" in i for i in r["issues"])


def test_calf_unweaned_stricter_limit():
    # unweaned calf max 9h
    r = _call(check_rest_water_feed_journey,
              species="cattle_calf_unweaned", drive_time_h=10.0,
              water_available_in_drive=True, ambient_temp_c=15)
    assert any("EXCEEDS" in i for i in r["issues"])


def test_pigs_long_drive_no_water_flagged():
    r = _call(check_rest_water_feed_journey,
              species="pigs", drive_time_h=20.0,
              water_available_in_drive=False, ambient_temp_c=20)
    assert any("water" in i.lower() for i in r["issues"])


def test_heat_stress_flagged():
    r = _call(check_rest_water_feed_journey,
              species="sheep", drive_time_h=6.0,
              water_available_in_drive=True, ambient_temp_c=33)
    assert any("heat stress" in i.lower() or "30C" in i for i in r["issues"])


def test_compliant_journey():
    r = _call(check_rest_water_feed_journey,
              species="cattle_adult", drive_time_h=8.0,
              rest_time_h=1.5,
              water_available_in_drive=True, feed_available_in_drive=True,
              ambient_temp_c=18, journey_total_h=9.0)
    assert r["compliant"] is True


# ─── 7. prepare_apha_inspection_pack ─────────────────────────────────

def test_apha_pack_inspection_ready():
    r = _call(prepare_apha_inspection_pack,
              operator_name="Top Tier Hauliers",
              fleet_size=5, species_authorised=["cattle"],
              has_authorisation=True, has_vehicle_approvals=True,
              has_driver_cofcs=True, has_journey_logs=True,
              has_gps_records=True, has_temperature_records=True,
              has_contingency_plan=True, operates_long_journey=True)
    assert r["grade"] == "A"


def test_apha_pack_missing_basics_fail():
    r = _call(prepare_apha_inspection_pack,
              operator_name="Risky Ltd", fleet_size=2,
              species_authorised=["sheep"], operates_long_journey=True)
    assert r["grade"] in ("F", "C")
    assert "Cheale" in r["advisory"]


def test_apha_pack_gb_to_ni_flags_windsor():
    r = _call(prepare_apha_inspection_pack,
              operator_name="NI Crossing Ltd",
              fleet_size=3, species_authorised=["cattle"],
              has_authorisation=True, has_vehicle_approvals=True,
              has_driver_cofcs=True,
              operates_long_journey=False,
              operates_gb_to_ni=True)
    assert any("TRACES" in a or "Windsor" in a for a in r["divergence_action_items"])


def test_apha_pack_gb_to_eu_flags_export_ban():
    r = _call(prepare_apha_inspection_pack,
              operator_name="Cross-Channel Ltd",
              fleet_size=10, species_authorised=["cattle", "sheep"],
              has_authorisation=True, has_vehicle_approvals=True,
              has_driver_cofcs=True, has_journey_logs=True,
              has_gps_records=True, has_temperature_records=True,
              has_contingency_plan=True,
              operates_long_journey=True, operates_gb_to_eu=True)
    assert any("Export" in a or "BANNED" in a or "slaughter" in a for a in r["divergence_action_items"])


# ─── tables + HMAC attestation ────────────────────────────────────────

def test_auth_types_has_both_tiers():
    assert "type_1" in AUTH_TYPES
    assert "type_2" in AUTH_TYPES


def test_loading_density_table_covers_5_species():
    species_in_table = {k.split("_")[0] for k in LOADING_DENSITY}
    # cattle, sheep, pigs, poultry, horses
    assert {"cattle", "sheep", "pigs", "poultry", "horses"} <= species_in_table


def test_rest_rules_covers_unweaned_calf():
    assert "cattle_calf_unweaned" in REST_RULES_HOURS


def test_vehicle_approval_table_has_pigs_ventilation():
    assert "ventilation" in VEHICLE_APPROVAL["pigs"].lower()


def test_uk_divergence_2024_lists_windsor():
    assert any("Windsor" in d or "TRACES" in d for d in UK_DIVERGENCE_2024)


def test_attestation_signed_and_versioned():
    r = _call(check_journey_log_long_journey, species="pigs",
              estimated_duration_h=3.0)
    assert r["issuer"] == "meok-livestock-welfare-transport-mcp"
    assert r["version"] == "1.0.0"
    assert "ts" in r and "sig" in r


def test_attestation_signed_when_hmac_set(monkeypatch):
    monkeypatch.setenv("MEOK_HMAC_SECRET", "test-secret-123")
    # reload so _HMAC_SECRET reads the env var at module load time
    import importlib, server as _s
    importlib.reload(_s)
    sig = _s._sign({"hello": "world"})
    assert sig != "unsigned-no-key-configured"
    assert len(sig) == 64  # sha256 hex


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
