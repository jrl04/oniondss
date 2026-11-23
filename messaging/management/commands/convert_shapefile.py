import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify


class Command(BaseCommand):
    help = "Convert a shapefile to a WGS84 GeoJSON layer for the staff field map."

    def add_arguments(self, parser):
        parser.add_argument("shapefile", type=Path)
        parser.add_argument("--name", help="Layer name shown on the field map.")
        parser.add_argument("--source-crs", help="Source CRS if the .prj file is missing or incorrect.")
        parser.add_argument("--encoding", help="DBF text encoding override, such as CP1252.")
        parser.add_argument("--ogr2ogr", default="ogr2ogr", help="Path to the GDAL ogr2ogr executable.")
        parser.add_argument("--replace", action="store_true", help="Replace an existing layer with the same name.")

    def handle(self, *, shapefile, name, source_crs, encoding, ogr2ogr, replace, **options):
        source = shapefile.resolve()
        if source.suffix.lower() != ".shp" or not source.is_file():
            raise CommandError("Provide an existing .shp file.")
        parts = {
            path.suffix.lower()
            for path in source.parent.iterdir()
            if path.stem == source.stem and path.is_file()
        }
        if not {".dbf", ".shx"}.issubset(parts):
            raise CommandError("Keep the matching .dbf and .shx files alongside the .shp file.")
        if not source_crs and ".prj" not in parts:
            raise CommandError("Provide a .prj file or specify the source CRS with --source-crs.")
        slug = slugify(name or source.stem)
        if not slug:
            raise CommandError("Supply a layer name containing letters or numbers.")

        directory = settings.MAP_GEOJSON_DIR
        destination = directory / f"{slug}.geojson"
        try:
            directory.mkdir(parents=True, exist_ok=True)
            if destination.exists() and not replace:
                raise FileExistsError
            with TemporaryDirectory(dir=directory) as staging:
                output = Path(staging) / destination.name
                command = [ogr2ogr, "-f", "GeoJSON", "-t_srs", "EPSG:4326", "-lco", "RFC7946=YES"]
                if source_crs:
                    command.extend(["-s_srs", source_crs])
                if encoding:
                    command.extend(["-oo", f"ENCODING={encoding}"])
                completed = subprocess.run([*command, str(output), str(source)], capture_output=True, text=True)
                if completed.returncode:
                    raise CommandError(completed.stderr.strip() or "GDAL could not convert the shapefile.")
                if replace:
                    os.replace(output, destination)
                else:
                    os.link(output, destination)
        except FileExistsError as exc:
            raise CommandError(f"Layer already exists. Use --replace to update {destination.name}.") from exc
        except FileNotFoundError as exc:
            raise CommandError(f"Could not find GDAL ogr2ogr or its output. Check --ogr2ogr. {exc}") from exc
        except OSError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Saved {destination}"))
