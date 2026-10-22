"""Streaming OSM tourism import with stable IDs, nearby-city matching and attribution.

Run with the backend on PYTHONPATH: python -m app.osm_import --download PATH
then python -m app.osm_import --input PATH. Re-runs update the same OSM IDs.
Uses pyosmium rather than implementing a PBF parser.
"""

import argparse
import datetime as dt
import hashlib
import gc
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
from sqlalchemy import select
from .db import SessionLocal, create_schema
from .models import Destination, MapPlace
from .travel_planning import distance_km

INDIA = "https://download.geofabrik.de/asia/india-latest.osm.pbf"
ATTRIBUTION = "© OpenStreetMap contributors"
LICENSE = "https://www.openstreetmap.org/copyright"


def download(path):
    path = Path(path).resolve()
    if path.exists():
        raise ValueError("Target already exists; refusing to overwrite an extract.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    if temporary.exists():
        raise ValueError("Partial extract already exists. Inspect it before retrying.")
    digest = hashlib.md5(usedforsecurity=False)
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        expected = client.get(INDIA + ".md5")
        expected.raise_for_status()
        with client.stream("GET", INDIA) as response:
            response.raise_for_status()
            with temporary.open("wb") as output:
                for index, chunk in enumerate(response.iter_bytes(1024 * 1024)):
                    output.write(chunk)
                    digest.update(chunk)
                    if index % 64 == 0:
                        print(f"Downloaded {index} MiB", flush=True)
        if digest.hexdigest() != expected.text.split()[0]:
            raise ValueError(
                "Geofabrik checksum mismatch; incomplete extract retained for diagnosis."
            )
    temporary.replace(path)
    return dict(path=str(path), md5=digest.hexdigest(), source=INDIA)


def ingest(path, db, *, max_places=None, location_index="flex_mem"):
    import osmium

    destinations = list(db.scalars(select(Destination)))
    count, batch = 0, 0
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()
    # Disk-backed node locations keep the country-sized import bounded in RAM.
    processor = (
        osmium.FileProcessor(str(path))
        .with_locations(location_index)
        .with_filter(osmium.filter.KeyFilter("tourism"))
    )
    for obj in processor:
        tags = dict(obj.tags)
        category = tags.get("tourism")
        if (
            not category
            or not tags.get("name")
            or category in {"hotel", "motel", "hostel", "guest_house", "information"}
        ):
            continue
        if obj.is_node():
            if not obj.location.valid():
                continue
            lat, lng = obj.location.lat, obj.location.lon
            kind = "node"
        elif obj.is_way():
            coords = [(n.lat, n.lon) for n in obj.nodes if n.location.valid()]
            if not coords:
                continue
            lat, lng = (
                sum(p[0] for p in coords) / len(coords),
                sum(p[1] for p in coords) / len(coords),
            )
            kind = "way"
        else:
            continue  # Relation geometry requires an area assembler; never invent it.
        nearest = (
            min(destinations, key=lambda d: distance_km(lat, lng, d.lat, d.lng))
            if destinations
            else None
        )
        distance = distance_km(lat, lng, nearest.lat, nearest.lng) if nearest else None
        identifier = kind + "/" + str(obj.id)
        row = db.get(MapPlace, identifier) or MapPlace(osm_id=identifier)
        row.name, row.category, row.lat, row.lng = (
            tags["name"][:250],
            category[:80],
            lat,
            lng,
        )
        row.destination_id = nearest.id if nearest and distance <= 100 else None
        row.tags = {
            key: value
            for key, value in tags.items()
            if key
            in {
                "tourism",
                "name",
                "name:en",
                "opening_hours",
                "wheelchair",
                "website",
                "fee",
                "ele",
                "wikidata",
            }
        }
        row.provenance = dict(
            source=INDIA,
            osm_url="https://www.openstreetmap.org/" + identifier,
            attribution=ATTRIBUTION,
            license=LICENSE,
            imported_at=stamp,
            version=obj.version,
            city_match="nearest catalog city within 100 km",
            distance_km=distance,
            coordinate_basis="node"
            if kind == "node"
            else "mean of way nodes; approximate",
        )
        db.add(row)
        count += 1
        batch += 1
        if batch >= 500:
            db.commit()
            batch = 0
            print(f"Imported {count} tourism features", flush=True)
        if max_places and count >= max_places:
            break
    db.commit()
    processor.node_location_storage.clear()
    del processor
    gc.collect()
    return dict(imported=count, attribution=ATTRIBUTION, license=LICENSE)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--location-index", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.download:
        print(download(args.download))
    if args.input:
        if not args.location_index:
            # pyosmium's file-backed maps can retain Windows handles for the
            # process lifetime. A child owns those handles; the parent removes
            # its private index only after that child exits.
            with TemporaryDirectory(
                prefix="osm-locations-", dir=args.input.resolve().parent
            ) as temporary:
                command = [
                    sys.executable,
                    "-m",
                    "app.osm_import",
                    "--input",
                    str(args.input),
                    "--location-index",
                    "sparse_file_array," + str(Path(temporary) / "nodes.idx"),
                ]
                if args.limit:
                    command += ["--limit", str(args.limit)]
                subprocess.run(command, check=True)
            return
        create_schema()
        with SessionLocal() as db:
            print(
                ingest(
                    args.input,
                    db,
                    max_places=args.limit,
                    location_index=args.location_index,
                )
            )


if __name__ == "__main__":
    main()
