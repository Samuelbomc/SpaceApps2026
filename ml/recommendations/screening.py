"""Compatibilidad explicable de cuatro requisitos numéricos, sin ranking de siembra."""

import hashlib

from packages.contracts.agronomy import (
    CropCatalog,
    CropScreening,
    CropScreeningContext,
    CropScreeningReport,
    RequirementCheck,
)

RULE_VERSION = "ecocrop-numeric-screening-v1"


def range_check(variable, value, requirement, missing_reason):
    if value is None:
        return RequirementCheck(
            variable=variable,
            status="unknown",
            value=None,
            unit=requirement.unit,
            explanation=missing_reason,
        )
    absolute, optimal = requirement.absolute, requirement.optimal
    if not absolute.minimum <= value <= absolute.maximum:
        status, reason = (
            "outside_absolute",
            f"Fuera del rango absoluto {absolute.minimum:g}–{absolute.maximum:g} {requirement.unit}.",
        )
    elif optimal.minimum <= value <= optimal.maximum:
        status, reason = (
            "optimal",
            f"Dentro del rango óptimo {optimal.minimum:g}–{optimal.maximum:g} {requirement.unit}.",
        )
    else:
        status, reason = (
            "within_absolute",
            "Dentro del rango absoluto, pero fuera del intervalo óptimo del catálogo.",
        )
    return RequirementCheck(
        variable=variable, status=status, value=value, unit=requirement.unit, explanation=reason
    )


def screen_catalog(catalog: CropCatalog, context: CropScreeningContext) -> CropScreeningReport:
    rainfall = context.annual_rainfall
    # Un total con huecos no representa la precipitación anual completa.
    annual_mm = (
        rainfall.total_mm
        if rainfall and rainfall.valid_days == (rainfall.end - rainfall.start).days + 1
        else None
    )
    assessments = []
    for crop in catalog.crops:
        checks = [
            range_check(
                "temperature",
                context.temperature.mean_c if context.temperature else None,
                crop.temperature,
                "Falta una temperatura media con periodo y procedencia identificados.",
            ),
            range_check(
                "annual_rainfall",
                annual_mm,
                crop.annual_rainfall,
                "Falta un acumulado anual completo; un pronóstico de días no sustituye mm/año.",
            ),
            range_check(
                "soil_ph", context.soil_ph, crop.soil_ph, "Falta una medición de pH del suelo."
            ),
        ]
        if context.altitude_m is None or crop.altitude_max_m is None:
            altitude = RequirementCheck(
                variable="altitude",
                status="unknown",
                value=context.altitude_m,
                unit="m",
                explanation="Falta la altitud del sitio o el límite máximo de altitud del cultivo.",
            )
        else:
            altitude = RequirementCheck(
                variable="altitude",
                value=context.altitude_m,
                unit="m",
                status="within_absolute"
                if context.altitude_m <= crop.altitude_max_m
                else "outside_absolute",
                explanation=f"Se comprueba únicamente el máximo reportado: {crop.altitude_max_m:g} m; no hay un óptimo ni mínimo definido.",
            )
        checks.append(altitude)
        status = (
            "outside_checked_ranges"
            if any(check.status == "outside_absolute" for check in checks)
            else "insufficient_data"
            if any(check.status == "unknown" for check in checks)
            else "within_checked_ranges"
        )
        limitations = list(catalog.limitations)
        limitations += [
            "Los límites letales requieren temperatura mínima y fase fenológica; no se evalúan con la temperatura media.",
            "Esta comparación de rangos no mide probabilidad de éxito, rendimiento o aptitud integral de siembra.",
        ]
        if context.temperature and context.temperature.kind == "forecast":
            days = (context.temperature.end - context.temperature.start).days + 1
            limitations.append(
                f"La temperatura pronosticada cubre {days} días; no caracteriza todo el ciclo de {crop.cycle_days.minimum:g}–{crop.cycle_days.maximum:g} días."
            )
        if "shared_species_requirements_not_variety_specific" in crop.quality_flags:
            limitations.append(
                "Este perfil comparte requisitos ECOCROP de especie; no demuestra diferencias entre fríjol arbustivo y voluble."
            )
        assessments.append(
            CropScreening(
                crop_id=crop.crop_id,
                crop_name=crop.crop_name,
                chain=crop.chain,
                ecocrop_code=crop.ecocrop_code,
                status=status,
                checks=checks,
                limitations=limitations,
            )
        )
    snapshot = hashlib.sha256(context.model_dump_json().encode()).hexdigest()
    return CropScreeningReport(
        catalog_version=catalog.version,
        rule_version=RULE_VERSION,
        input_snapshot_id=snapshot,
        context=context,
        crops=assessments,
    )
