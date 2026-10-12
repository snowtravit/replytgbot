#!/usr/bin/env python3
"""Package an already checked-out and built release; no installs or network use."""

import argparse
import hashlib
import io
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile


REPOSITORIES = ("UrWeather", "snow-local-ide", "replytgbot", "bobby-26.3")


def tracked_paths(source):
    output = subprocess.check_output(["git", "ls-files", "-z"], cwd=source)
    return [Path(name) for name in output.decode("utf-8").split("\0") if name]


def check_path(path):
    parts = path.parts
    if path.is_absolute() or ".." in parts:
        raise ValueError(f"Unsafe archive path: {path}")
    if "node_modules" in parts or any(
        name == ".env" or name.startswith(".env.") and name != ".env.example"
        or ".session" in name
        for name in parts
    ):
        raise ValueError(f"Private or installed dependency file in archive: {path}")


def archive_source(source, output, prefix):
    for path in tracked_paths(source):
        check_path(path)
    subprocess.run(
        ["git", "archive", "--format=zip", f"--prefix={prefix}/", "-o", str(output), "HEAD"],
        cwd=source,
        check=True,
    )


def dependency_notices(package_roots, target):
    sections = [
        "Dependency licenses from the installed build. This inventory includes build tools.\n"
        "These notices do not replace the project license or grant rights to existing media.\n"
    ]
    for label, package in package_roots:
        directory = package / "node_modules"
        if not directory.is_dir():
            raise FileNotFoundError(f"Install build dependencies before packaging: {directory}")
        found = []
        for parent, folders, files in os.walk(directory):
            folders[:] = sorted(name for name in folders if name not in {".cache", ".bin", ".git"})
            for filename in sorted(files):
                lower = filename.lower()
                if lower.startswith(("license", "licence", "copying", "notice")) or "thirdpartynotice" in lower:
                    file = Path(parent) / filename
                    if file.is_file():
                        found.append(file)
        if not found:
            raise ValueError(f"No dependency license files found: {directory}")
        for file in sorted(found):
            sections.append(f'\n{"=" * 72}\n{label}: {file.relative_to(directory).as_posix()}\n{"=" * 72}\n')
            sections.append(file.read_text(encoding="utf-8", errors="replace"))
            sections.append("\n")
    target.write_text("".join(sections), encoding="utf-8")


def extract_source(source, destination):
    archive_bytes = subprocess.check_output(["git", "archive", "--format=zip", "HEAD"], cwd=source)
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        for name in archive.namelist():
            check_path(Path(name))
        archive.extractall(destination)


def zip_tree(directory, output):
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for file in sorted(directory.rglob("*")):
            if file.is_file():
                relative = file.relative_to(directory)
                check_path(relative)
                archive.write(file, Path(directory.name) / relative)


def sha256(file):
    digest = hashlib.sha256()
    with file.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def package(source, output, repo, version):
    source = source.resolve()
    output = output.resolve()
    version = version.removeprefix("v")
    if not re.fullmatch(r"[0-9][A-Za-z0-9.+_-]*", version):
        raise ValueError("Version must begin with a digit and use letters, digits, dots, +, _ or -")
    output.mkdir(parents=True, exist_ok=True)
    basename = "bobby" if repo == "bobby-26.3" else repo
    files = [output / f"{basename}-v{version}-source.zip"]
    if repo == "bobby-26.3":
        files[0] = output / f"bobby-{version}-source.zip"
    archive_source(source, files[0], f"{repo}-{version}")

    with tempfile.TemporaryDirectory(prefix="release-package-") as temporary:
        staging = Path(temporary)
        if repo == "UrWeather":
            stage = staging / f"UrWeather-v{version}-web"
            shutil.copytree(source / "UrWeather" / "dist", stage)
            for name in ("README.md", "CHANGELOG.md", "LICENSE", "THIRD_PARTY_NOTICES.md"):
                shutil.copy2(source / name, stage / name)
            shutil.copytree(source / "docs", stage / "docs")
            dependency_notices([("UrWeather", source / "UrWeather")], stage / "THIRD_PARTY_DEPENDENCY_LICENSES.txt")
            files.append(output / f"UrWeather-v{version}-web.zip")
            zip_tree(stage, files[-1])
        elif repo == "snow-local-ide":
            stage = staging / f"SNOW-IDE-v{version}"
            stage.mkdir()
            extract_source(source, stage)
            roots = []
            for component in ("backend", "frontend"):
                package_root = source / "SNOW CODING CORP" / component
                shutil.copytree(package_root / "dist", stage / "SNOW CODING CORP" / component / "dist", dirs_exist_ok=True)
                roots.append((component, package_root))
            dependency_notices(roots, stage / "THIRD_PARTY_DEPENDENCY_LICENSES.txt")
            files.append(output / f"SNOW-IDE-v{version}.zip")
            zip_tree(stage, files[-1])
        elif repo == "bobby-26.3":
            jar = source / "build" / "libs" / f"bobby-{version}.jar"
            files.append(output / jar.name)
            shutil.copy2(jar, files[-1])
            for name, filename in (("LICENSE.LESSER.md", "Bobby-LGPL-3.0.txt"), ("LICENSE.md", "Bobby-GPL-3.0.txt")):
                files.append(output / filename)
                shutil.copy2(source / name, files[-1])

    for file in files:
        if file.suffix == ".zip":
            with zipfile.ZipFile(file) as archive:
                for name in archive.namelist():
                    check_path(Path(name))
                if archive.testzip() is not None:
                    raise ValueError(f"Archive checksum validation failed: {file}")
    checksums = output / "SHA256SUMS.txt"
    checksums.write_text("".join(f"{sha256(file)}  {file.name}\n" for file in sorted(files)), encoding="utf-8")
    for file in [*files, checksums]:
        print(file.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("repo_name", choices=REPOSITORIES)
    parser.add_argument("version")
    args = parser.parse_args()
    package(args.source_dir, args.output_dir, args.repo_name, args.version)


if __name__ == "__main__":
    main()
