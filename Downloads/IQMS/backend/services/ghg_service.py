"""
============================================================
 GHG Service — Calcul des émissions de gaz à effet de serre
 Facteurs d'émission EPA (2023)
============================================================
"""
from __future__ import annotations
from typing import Any

# ── Facteurs d'émission EPA ──────────────────────────────────
# Source : EPA eGRID 2023 / EPA Emission Factors for GHG Inventories
FACTOR_ELECTRICITY_KWH = 0.386   # kgCO2e / kWh  (réseau Nord-Américain moyen)
FACTOR_GAS_M3          = 2.04    # kgCO2e / m³   (gaz naturel)
FACTOR_FUEL_LITER      = 2.68    # kgCO2e / L    (fioul de chauffage No. 2)


def calc_co2e_kg(
    electricity_kwh: float = 0.0,
    gas_m3: float = 0.0,
    fuel_liters: float = 0.0,
) -> dict[str, Any]:
    """Retourne le détail des émissions par source (en kg CO2e)."""
    elec_kg  = electricity_kwh * FACTOR_ELECTRICITY_KWH
    gas_kg   = gas_m3          * FACTOR_GAS_M3
    fuel_kg  = fuel_liters     * FACTOR_FUEL_LITER
    total_kg = elec_kg + gas_kg + fuel_kg

    return {
        "electricity_kwh":  round(electricity_kwh, 3),
        "gas_m3":           round(gas_m3, 3),
        "fuel_liters":      round(fuel_liters, 3),
        "electricity_kg":   round(elec_kg, 3),
        "gas_kg":           round(gas_kg, 3),
        "fuel_kg":          round(fuel_kg, 3),
        "total_kg":         round(total_kg, 3),
        "factors": {
            "electricity_kwh": FACTOR_ELECTRICITY_KWH,
            "gas_m3":          FACTOR_GAS_M3,
            "fuel_liter":      FACTOR_FUEL_LITER,
        },
    }


def calc_co2e_tonne(
    electricity_kwh: float = 0.0,
    gas_m3: float = 0.0,
    fuel_liters: float = 0.0,
) -> float:
    """Retourne le total des émissions en tonnes CO2e (tCO2e)."""
    detail = calc_co2e_kg(electricity_kwh, gas_m3, fuel_liters)
    return round(detail["total_kg"] / 1000.0, 6)


def aggregate_readings(readings: list[Any]) -> dict[str, Any]:
    """
    Agrège une liste d'objets EnergyReading ORM en rapport d'inventaire.
    Fonctionne avec n'importe quel objet ayant les attributs :
      electricity_kwh, gas_m3, fuel_liters, period_start, period_end
    """
    if not readings:
        return {
            "reading_count": 0,
            "total_electricity_kwh": 0.0,
            "total_gas_m3": 0.0,
            "total_fuel_liters": 0.0,
            "emissions": calc_co2e_kg(0, 0, 0),
            "period_start": None,
            "period_end": None,
        }

    total_elec  = sum(r.electricity_kwh          for r in readings)
    total_gas   = sum((r.gas_m3       or 0.0)    for r in readings)
    total_fuel  = sum((r.fuel_liters  or 0.0)    for r in readings)

    starts = [r.period_start for r in readings if r.period_start]
    ends   = [r.period_end   for r in readings if r.period_end]

    return {
        "reading_count":         len(readings),
        "total_electricity_kwh": round(total_elec,  3),
        "total_gas_m3":          round(total_gas,   3),
        "total_fuel_liters":     round(total_fuel,  3),
        "emissions":             calc_co2e_kg(total_elec, total_gas, total_fuel),
        "period_start":          min(starts).isoformat() if starts else None,
        "period_end":            max(ends).isoformat()   if ends   else None,
    }


def hvac_recommendations(
    aqi: float = 0.0,
    co_ppm: float = 0.0,
    temperature: float = 20.0,
    humidity: float = 50.0,
    electricity_kwh_recent: float = 0.0,
) -> list[dict[str, Any]]:
    """
    Recommandations HVAC enrichies avec économies estimées.
    Retourne une liste de recommandations triées par priorité.
    """
    recs: list[dict[str, Any]] = []

    # ── Qualité de l'air ──────────────────────────────────────
    if aqi > 150:
        recs.append({
            "priority":              "critical",
            "icon":                  "alert-triangle",
            "color":                 "red",
            "category":              "air_quality",
            "title":                 "Qualité de l'air critique — action immédiate",
            "text":                  "Passez en mode ventilation forcée (100 %). Vérifiez et remplacez les filtres HVAC.",
            "estimated_saving_pct":  0,
        })
    elif aqi > 100:
        recs.append({
            "priority":              "high",
            "icon":                  "wind",
            "color":                 "orange",
            "category":              "air_quality",
            "title":                 "Qualité de l'air dégradée — augmentez la ventilation",
            "text":                  "Augmentez le débit d'air frais à 60 %. Vérifiez le colmatage des filtres.",
            "estimated_saving_pct":  0,
        })
    elif aqi <= 50:
        recs.append({
            "priority":              "info",
            "icon":                  "check-circle",
            "color":                 "green",
            "category":              "air_quality",
            "title":                 "Excellente qualité de l'air",
            "text":                  "Vous pouvez réduire le débit de ventilation à 30 % pour économiser de l'énergie.",
            "estimated_saving_pct":  15,
        })

    # ── CO ────────────────────────────────────────────────────
    if co_ppm > 9:
        recs.append({
            "priority":              "critical",
            "icon":                  "alert-octagon",
            "color":                 "red",
            "category":              "co",
            "title":                 f"CO élevé : {co_ppm:.1f} ppm — urgence",
            "text":                  "Seuil OMS dépassé (9 ppm). Activez purge maximale et vérifiez les appareils à combustion.",
            "estimated_saving_pct":  0,
        })
    elif co_ppm > 4:
        recs.append({
            "priority":              "medium",
            "icon":                  "cloud",
            "color":                 "orange",
            "category":              "co",
            "title":                 f"CO modéré : {co_ppm:.1f} ppm",
            "text":                  "Augmentez la ventilation et vérifiez les sources de combustion à proximité.",
            "estimated_saving_pct":  0,
        })

    # ── Température ───────────────────────────────────────────
    if temperature > 28:
        recs.append({
            "priority":              "high",
            "icon":                  "thermometer-sun",
            "color":                 "orange",
            "category":              "temperature",
            "title":                 f"Température élevée : {temperature:.1f} °C",
            "text":                  "Abaissez la consigne de climatisation à 24 °C. Chaque degré économise ~3 % d'énergie.",
            "estimated_saving_pct":  3 * max(0, int(temperature - 24)),
        })
    elif temperature < 18:
        recs.append({
            "priority":              "high",
            "icon":                  "thermometer-snowflake",
            "color":                 "blue",
            "category":              "temperature",
            "title":                 f"Température basse : {temperature:.1f} °C",
            "text":                  "Augmentez la consigne de chauffage à 20 °C. Vérifiez l'isolation du bâtiment.",
            "estimated_saving_pct":  0,
        })
    else:
        recs.append({
            "priority":              "info",
            "icon":                  "thermometer",
            "color":                 "green",
            "category":              "temperature",
            "title":                 f"Température optimale : {temperature:.1f} °C",
            "text":                  "La plage 18–24 °C est maintenue. Envisagez une programmation horaire pour réduire les émissions.",
            "estimated_saving_pct":  8,
        })

    # ── Humidité ─────────────────────────────────────────────
    if humidity > 70:
        recs.append({
            "priority":              "medium",
            "icon":                  "droplets",
            "color":                 "blue",
            "category":              "humidity",
            "title":                 f"Humidité excessive : {humidity:.0f} %",
            "text":                  "Activez la déshumidification. Risque de moisissures et de dégradation de la qualité de l'air.",
            "estimated_saving_pct":  5,
        })
    elif humidity < 30:
        recs.append({
            "priority":              "medium",
            "icon":                  "droplet",
            "color":                 "yellow",
            "category":              "humidity",
            "title":                 f"Air trop sec : {humidity:.0f} %",
            "text":                  "Activez l'humidification. La plage idéale est 40–60 %.",
            "estimated_saving_pct":  0,
        })

    # ── Consommation électrique ───────────────────────────────
    if electricity_kwh_recent > 0:
        # Seuil indicatif : >500 kWh/période → potentiel d'optimisation
        if electricity_kwh_recent > 500:
            recs.append({
                "priority":              "medium",
                "icon":                  "zap",
                "color":                 "yellow",
                "category":              "energy",
                "title":                 f"Consommation élevée : {electricity_kwh_recent:.0f} kWh",
                "text":                  "Programmez les équipements HVAC en dehors des heures de pointe. Objectif : réduire de 10–15 %.",
                "estimated_saving_pct":  12,
            })
        elif electricity_kwh_recent > 200:
            recs.append({
                "priority":              "low",
                "icon":                  "zap",
                "color":                 "green",
                "category":              "energy",
                "title":                 f"Consommation modérée : {electricity_kwh_recent:.0f} kWh",
                "text":                  "Bonne performance. Vérifiez les réglages de ventilation nocturne pour optimiser davantage.",
                "estimated_saving_pct":  5,
            })

    # Trier : critical > high > medium > low > info
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    recs.sort(key=lambda r: priority_order.get(r["priority"], 99))

    return recs
