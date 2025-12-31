"""
csv_mapper.py

Reusable utilities for mapping typed Python objects to/from CSV files.

Features:
- Type-driven conversion via annotations
- Optional fields support
- Empty value handling
- Date & time format inference
- Enum support
- Boolean support
- Row-level error collection
- Round-trip CSV writing
"""

import csv
from dataclasses import fields, is_dataclass
from datetime import datetime, date, time
from typing import get_origin, get_args, Union, List, Tuple, Type, Set
from enum import Enum

SET_SEPARATOR = ";"

CSV_SEP = ";"

# =========================
# Type helpers
# =========================

def is_optional(t):
	return get_origin(t) is Union and type(None) in get_args(t)


def unwrap_optional(t):
	return next(arg for arg in get_args(t) if arg is not type(None))


def is_string_set(t):
	return get_origin(t) is set and get_args(t) == (str,)

def get_field_types(cls: Type) -> dict:
	if is_dataclass(cls):
		return {f.name: f.type for f in fields(cls)}
	return cls.__annotations__


# =========================
# Parsing helpers
# =========================

_DATE_FORMATS = (
	"%Y-%m-%d",
	"%d/%m/%Y",
	"%m/%d/%Y",
)

_TIME_FORMATS = (
	"%H:%M:%S",
	"%H:%M",
)


def parse_date(value: str) -> date:
	for fmt in _DATE_FORMATS:
		try:
			return datetime.strptime(value, fmt).date()
		except ValueError:
			pass
	raise ValueError(f"Invalid date format: '{value}'")


def parse_time(value: str) -> time:
	for fmt in _TIME_FORMATS:
		try:
			return datetime.strptime(value, fmt).time()
		except ValueError:
			pass
	raise ValueError(f"Invalid time format: '{value}'")


def parse_string_set(value: str) -> Set[str]:
	if value == "":
		return set()
	return {v.strip() for v in value.split(SET_SEPARATOR) if v.strip()}

def convert_value(value: str, target_type):
	if value == "" or value is None:
		return None

	# ---- bool ----
	if target_type is bool:
		v = value.strip().lower()
		if v in ("true", "1", "yes", "y", "t"):
			return True
		if v in ("false", "0", "no", "n", "f"):
			return False
		raise ValueError(f"Invalid boolean: '{value}'")

	# ---- enum ----
	if isinstance(target_type, type) and issubclass(target_type, Enum):
		try:
			if value in target_type.__members__:
				return target_type[value]
			return target_type(value)
		except Exception:
			valid = ", ".join(e.name for e in target_type)
			raise ValueError(f"Invalid enum value '{value}'. Valid: {valid}")

	# ---- set[str] ----
	if is_string_set(target_type):
		return parse_string_set(value)

	# ---- primitives ----
	if target_type is int:
		return int(value)
	if target_type is float:
		return float(value.replace("€",""))
	if target_type is str:
		return value
	if target_type is date:
		return parse_date(value)
	if target_type is time:
		return parse_time(value)

	raise TypeError(f"Unsupported type: {target_type}")


# =========================
# CSV → Objects
# =========================

def load_objects_from_csv(
	csv_path: str,
	cls: Type,
	renames: dict[str,str] = None
) -> Tuple[List[object], List[dict]]:
	"""
	Returns (objects, errors)

	errors: [
		{
			"row": int,
			"errors": [str, ...],
			"data": original_row_dict
		}
	]
	"""
	objects = []
	errors = []

	field_types = get_field_types(cls)

	with open(csv_path, newline="", encoding="utf-8") as f:
		reader = csv.DictReader(f, delimiter=CSV_SEP)

		for row_num, row in enumerate(reader, start=2):
			kwargs = {}
			row_errors = []

			for name, field_type in field_types.items():
				raw = (row.get(name) or row.get(name.upper()) or "").strip()
				if raw == "":
					if renames is not None and name in renames:
						v = renames[name]
						raw = (row.get(v) or row.get(v.upper()) or "").strip()
				try:
					if is_optional(field_type):
						inner = unwrap_optional(field_type)
						kwargs[name] = None if raw == "" else convert_value(raw, inner)
					else:
						if raw == "":
							raise ValueError("Required value missing")
						kwargs[name] = convert_value(raw, field_type)
				except Exception as e:
					row_errors.append(f"{name}: {e}")

			if row_errors:
				errors.append({
					"row": row_num,
					"errors": row_errors,
					"data": row
				})
			else:
				objects.append(cls(**kwargs))

	return objects, errors


# =========================
# Objects → CSV
# =========================

def format_value(value) -> str:
	if value is None:
		return ""

	if isinstance(value, bool):
		return "true" if value else "false"

	if isinstance(value, Enum):
		return value.name

	if isinstance(value, date):
		return value.isoformat()

	if isinstance(value, time):
		return value.strftime("%H:%M")

	if isinstance(value, set):
		return SET_SEPARATOR.join(sorted(value))

	return str(value)


def write_objects_to_csv(
	csv_path: str,
	objects: List[object],
	cls: Type,
	renames: dict[str,str] = None,
	skip: set[str] = set([])
):
	field_names = list(get_field_types(cls).keys())
	r = [x for x in field_names if not x in skip]
	field_names = r

	with open(csv_path, "w", newline="", encoding="utf-8") as f:
		hdrnames = [f.upper() for f in field_names]
		if renames is not None:
			hdrnames = [name for name in field_names]
			for i, n in enumerate(hdrnames):
				if n in renames:
					hdrnames[i] = renames[n]
				hdrnames[i] = hdrnames[i].upper()

		writer = csv.DictWriter(f, fieldnames=hdrnames, delimiter=CSV_SEP)
		writer.writeheader()
		if not objects:
			return
		writer = csv.DictWriter(f, fieldnames=field_names,
			quotechar='"',
			quoting = csv.QUOTE_ALL,
			delimiter=CSV_SEP)
		for obj in objects:
			writer.writerow({
				name: format_value(getattr(obj, name))
				for name in field_names
			})
