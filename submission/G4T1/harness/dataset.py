"""Dataset loader: the only code that knows the GeoNames file format."""
from dataclasses import dataclass
from pathlib import Path

COLUMNS = 19  # GeoNames tab-separated record; empty columns are preserved.


class DatasetError(ValueError):
    pass


@dataclass(frozen=True)
class Place:
    geoname_id: int
    name: str
    lat: float
    lon: float
    feature_class: str


def load_places(path):
    """Return a list of Place from a GeoNames extract, rejecting malformed rows."""
    places = []
    with Path(path).open(encoding="utf-8") as f:
        for number, line in enumerate(f, start=1):
            line = line.rstrip("\r\n")
            if not line:
                continue
            cols = line.split("\t")
            if len(cols) != COLUMNS:
                raise DatasetError(
                    f"{path}: line {number}: expected {COLUMNS} columns, found {len(cols)}")
            try:
                place = Place(int(cols[0]), cols[1], float(cols[4]), float(cols[5]), cols[6])
            except ValueError:
                raise DatasetError(
                    f"{path}: line {number}: geoname id, latitude or longitude is not a number") from None
            if not (-90 <= place.lat <= 90 and -180 <= place.lon <= 180):
                raise DatasetError(f"{path}: line {number}: coordinates out of range")
            places.append(place)
    return places
