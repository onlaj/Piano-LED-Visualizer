from pathlib import Path, PurePosixPath, PureWindowsPath


ALLOWED_SONG_EXTENSIONS = {"mid", "musicxml", "mxl", "xml", "abc"}


class SongFileError(ValueError):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def validate_song_filename(filename, allowed_extensions=None):
    if filename is None:
        raise SongFileError("missing song name")

    name = str(filename).strip()
    if not name:
        raise SongFileError("missing song name")

    if "\x00" in name:
        raise SongFileError("invalid song name")

    if "/" in name or "\\" in name:
        raise SongFileError("song name must not contain path separators")

    if name in {".", ".."} or ".." in Path(name).parts:
        raise SongFileError("song name must not contain path traversal")

    if ":" in name or PureWindowsPath(name).drive:
        raise SongFileError("song name must not contain a drive or scheme")

    if PurePosixPath(name).is_absolute() or PureWindowsPath(name).is_absolute():
        raise SongFileError("song name must be relative")

    allowed = allowed_extensions or ALLOWED_SONG_EXTENSIONS
    suffix = Path(name).suffix.lower().lstrip(".")
    if suffix not in allowed:
        raise SongFileError("unsupported song extension")

    return name


def resolve_song_path(filename, base_dir="Songs", must_exist=False, allowed_extensions=None):
    name = validate_song_filename(filename, allowed_extensions=allowed_extensions)
    base_path = Path(base_dir).resolve()
    resolved = (base_path / name).resolve()

    try:
        resolved.relative_to(base_path)
    except ValueError as exc:
        raise SongFileError("song path escapes Songs directory") from exc

    if must_exist and not resolved.is_file():
        raise SongFileError(f"{name} not found", status_code=404)

    return resolved


def resolve_song_cache_path(filename, base_dir="Songs", must_exist=False):
    name = validate_song_filename(filename, allowed_extensions={"mid"})
    cache_path = (Path(base_dir).resolve() / "cache" / f"{name}.p").resolve()
    cache_dir = (Path(base_dir).resolve() / "cache").resolve()

    try:
        cache_path.relative_to(cache_dir)
    except ValueError as exc:
        raise SongFileError("cache path escapes Songs cache directory") from exc

    if must_exist and not cache_path.is_file():
        raise SongFileError(f"{name} cache not found", status_code=404)

    return cache_path


def is_bundle_main(filename):
    name = validate_song_filename(filename, allowed_extensions={"mid"})
    return Path(name).stem.endswith("_main")


def bundle_prefix(filename):
    name = validate_song_filename(filename, allowed_extensions={"mid"})
    stem = Path(name).stem
    if stem.endswith("_main"):
        return stem[: -len("_main")]
    return stem


def bundle_member_paths(filename, base_dir="Songs"):
    name = validate_song_filename(filename, allowed_extensions={"mid"})
    songs_dir = Path(base_dir).resolve()
    prefix = bundle_prefix(name)
    expected_prefix = f"{prefix}_"

    if not songs_dir.exists():
        return []

    members = []
    for path in songs_dir.iterdir():
        if not path.is_file():
            continue
        if not path.name.startswith(expected_prefix):
            continue
        if path.suffix.lower().lstrip(".") not in ALLOWED_SONG_EXTENSIONS:
            continue
        members.append(path.resolve())
    return sorted(members, key=lambda path: path.name.lower())
