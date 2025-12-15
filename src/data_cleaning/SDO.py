from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any
import math

from pydantic import BaseModel, Field, validator


class LocationRecord(BaseModel):
    """Structured Data Object for a location/dimension row.

    Fields mirror the proposed dataclass in your design. Kept simple so it can
    be resolved to a dimension table (surrogate key assigned during ingest).
    """

    country: str
    iso2: Optional[str] = None
    iso3: Optional[str] = None
    iso_numeric: Optional[int] = None
    who_region: Optional[str] = None

    @validator("country")
    def country_must_not_be_blank(cls, v: str) -> str:
        if not v or not str(v).strip():
            raise ValueError("country must be provided and non-empty")
        return v.strip()


class IndicatorRecord(BaseModel):
    """Structured Data Object for an indicator/variable.

    This maps a variable name from the data dictionary into a compact record
    that can be stored in an indicator dimension.
    """

    variable_name: str
    dataset_group: Optional[str] = None
    definition: Optional[str] = None
    code_list: Optional[str] = None

    @validator("variable_name")
    def variable_name_not_empty(cls, v: str) -> str:
        if not v or not str(v).strip():
            raise ValueError("variable_name must be provided and non-empty")
        return v.strip()


class OutcomeFactRecord(BaseModel):
    """Structured Data Object representing a single fact (long/tidy).

    The ingest pipeline is expected to resolve `location_id` and
    `indicator_id` (surrogate integer keys) before inserting into a database.
    """

    location_id: int
    indicator_id: int
    year: int
    value: Optional[float] = None
    rep_meth: Optional[str] = None
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    flags: Optional[Dict[str, Any]] = None
    source_file: Optional[str] = None
    source_col: Optional[str] = None

    @validator("year")
    def year_in_plausible_range(cls, v: int) -> int:
        if v is None:
            raise ValueError("year is required")
        if v < 1900 or v > 2100:
            raise ValueError("year out of plausible range: %s" % v)
        return int(v)

    @validator("value")
    def value_non_negative(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        try:
            fv = float(v)
        except Exception:
            raise ValueError("value must be numeric or None")
        if fv < 0:
            raise ValueError("value must be non-negative")
        return fv


def location_from_row(row: Dict[str, Any]) -> LocationRecord:
    """Create LocationRecord from a cleaned row dict/series.

    Expects keys like `country`, `iso2`, `iso3`, `iso_numeric`, `g_whoregion`.
    """
    def _none_if_nan(v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, float) and math.isnan(v):
            return None
        return v

    return LocationRecord(
        country=row.get("country"),
        iso2=_none_if_nan(row.get("iso2")),
        iso3=_none_if_nan(row.get("iso3")),
        iso_numeric=_safe_int(row.get("iso_numeric")),
        who_region=_none_if_nan(row.get("g_whoregion")) or _none_if_nan(row.get("who_region")) or None,
    )


def indicator_from_dict(d: Dict[str, Any]) -> IndicatorRecord:
    """Create IndicatorRecord from a dictionary row (eg. from data dictionary CSV).

    Expects keys `variable_name`, `dataset`, `definition`, `code_list`.
    """
    def _code_list_clean(val: Any) -> Optional[str]:
        if val is None:
            return None
        if isinstance(val, float) and math.isnan(val):
            return None
        return str(val)

    return IndicatorRecord(
        variable_name=d.get("variable_name") or d.get("variable") or d.get("variableName"),
        dataset_group=d.get("dataset") or None,
        definition=d.get("definition") or None,
        code_list=_code_list_clean(d.get("code_list") or d.get("code list")),
    )


def outcomefact_from_values(
    location_id: int,
    indicator_id: int,
    year: int,
    value: Optional[float],
    rep_meth: Optional[str] = None,
    *,
    source_file: Optional[str] = None,
    source_col: Optional[str] = None,
    flags: Optional[Dict[str, Any]] = None,
) -> OutcomeFactRecord:
    return OutcomeFactRecord(
        location_id=location_id,
        indicator_id=indicator_id,
        year=year,
        value=value,
        rep_meth=rep_meth,
        ingested_at=datetime.utcnow(),
        flags=flags,
        source_file=source_file,
        source_col=source_col,
    )


def _safe_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        if v == "":
            return None
        return int(v)
    except Exception:
        return None


__all__ = [
    "LocationRecord",
    "IndicatorRecord",
    "OutcomeFactRecord",
    "location_from_row",
    "indicator_from_dict",
    "outcomefact_from_values",
]
