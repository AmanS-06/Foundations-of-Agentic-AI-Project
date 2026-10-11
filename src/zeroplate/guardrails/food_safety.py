"""Can a leftover batch be reused? Rule C9, from the FSSAI catering guide (Oct 2017).

    held hot at >= 65 C           safe if eaten within 24 h of cooking
    chilled at <= 5 C             safe if within 24 h, and not already reheated (reheat once)
    anything else (65 C > t > 5 C, e.g. room temperature)
                                  only within 2 h of cooking, and only if never reheated
    any batch already reheated    gravies, meat, poultry, fish: reheat only once -> discard

Age is measured at the time the food would be served on the plan date.
"""

from __future__ import annotations

from datetime import date, datetime, time

from zeroplate import config
from zeroplate.schemas import Holding, LeftoverBatch


def service_time(plan_date: date) -> datetime:
    """When reused food would be served (lunch on the plan date)."""
    return datetime.combine(plan_date, time(hour=config.SERVICE_HOUR))


def reuse_verdict(batch: LeftoverBatch, plan_date: date) -> tuple[bool, str]:
    """(safe, reason) for reusing `batch` on `plan_date`."""
    age_h = (service_time(plan_date) - batch.cooked_at).total_seconds() / 3600
    if batch.reheated_count >= config.MAX_REHEATS:
        return False, f"already reheated {batch.reheated_count}x (FSSAI: reheat only once)"
    if age_h > config.MAX_AGE_HOURS:
        return False, f"{age_h:.0f} h old (FSSAI: eat within {config.MAX_AGE_HOURS} h)"
    if batch.holding is Holding.HOT and batch.temp_c >= config.HOT_HOLD_MIN_C:
        return True, f"held hot at {batch.temp_c:g} C, {age_h:.0f} h old"
    if batch.holding is Holding.CHILLED and batch.temp_c <= config.CHILL_MAX_C:
        return True, f"chilled at {batch.temp_c:g} C, {age_h:.0f} h old, reheat once to 75 C"
    if age_h <= config.BELOW_HOT_HOLD_MAX_HOURS:
        return True, f"only {age_h:.1f} h below 65 C; reheat once to 75 C"
    return False, (
        f"kept at {batch.temp_c:g} C for {age_h:.0f} h (FSSAI: below 65 C, eat within "
        f"{config.BELOW_HOT_HOLD_MAX_HOURS} h or discard)"
    )


def relevant_batches(batches: list[LeftoverBatch], plan_date: date) -> list[LeftoverBatch]:
    """Batches cooked in the 48 h before service on the plan date (older ones are irrelevant)."""
    serve = service_time(plan_date)
    return [b for b in batches if 0 < (serve - b.cooked_at).total_seconds() <= 48 * 3600]
