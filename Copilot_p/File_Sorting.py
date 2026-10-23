#!/usr/bin/env python3
"""Sort the files in a folder into subfolders named for their extensions."""

import argparse
from pathlib import Path


def destination_for(source: Path, folder: Path, reserved: set[Path]) -> Path:
    extension = source.suffix[1:].upper() if source.suffix else "No Extension"
    destination_folder = folder / extension
    candidate = destination_folder / source.name
    counter = 1

    while candidate.exists() or candidate in reserved:
        candidate = destination_folder / f"{source.stem} ({counter}){source.suffix}"
        counter += 1

    reserved.add(candidate)
    return candidate


def sort_files(folder: Path, dry_run: bool) -> int:
    script_path = Path(__file__).resolve()
    files = sorted(
        (
            path
            for path in folder.iterdir()
            if path.is_file() and path.resolve() != script_path
        ),
        key=lambda path: path.name.casefold(),
    )
    reserved: set[Path] = set()
    errors = 0

    if not files:
        print(f"No files to sort in: {folder}")
        return 0

    for source in files:
        destination = destination_for(source, folder, reserved)
        if dry_run:
            print(f"Would move: {source.name} -> {destination.parent.name}/{destination.name}")
            continue

        try:
            destination.parent.mkdir(exist_ok=True)
            source.rename(destination)
            print(f"Moved: {source.name} -> {destination.parent.name}/{destination.name}")
        except OSError as error:
            errors += 1
            print(f"Error moving {source.name}: {error}")

    if dry_run:
        print(f"\nPreview only: {len(files)} file(s) would be moved. Use --apply to move them.")
    else:
        print(f"\nFinished: {len(files) - errors} moved, {errors} error(s).")

    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Move files into subfolders named by file extension."
    )
    parser.add_argument(
        "folder",
        type=Path,
        nargs="?",
        help="folder whose files should be sorted (only its top-level files are considered)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="perform the moves; without this option, show a preview only",
    )
    args = parser.parse_args()
    folder = args.folder
    interactive_folder = folder is None
    if folder is None:
        folder_input = input("Enter the folder path to sort: ").strip()
        if not folder_input:
            parser.error("a folder path is required")
        folder = Path(folder_input)

    folder = folder.expanduser()

    if not folder.exists():
        parser.error(f"folder does not exist: {folder}")
    if not folder.is_dir():
        parser.error(f"not a folder: {folder}")

    return sort_files(folder, dry_run=not (args.apply or interactive_folder))


if __name__ == "__main__":
    raise SystemExit(main())