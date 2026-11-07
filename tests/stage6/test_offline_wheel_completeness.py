"""The offline wheel set must actually satisfy what the application imports.

``installer/README.md`` claims the target Server installs only from
``installer/wheels`` with ``--no-index``. Nothing checked that claim, and the
set shipped without ``httpx`` even though ``requirements.txt`` lists it and
``packages/hms_license/client.py`` imports it - so the documented offline
install died on ``ERROR: No matching distribution found for httpx>=0.27.0``.
``production_setup_requirements`` only asks whether at least one ``*.whl``
exists, which an incomplete set trivially satisfies.

Two halves, because the wheels themselves are gitignored and a fresh clone has
none of them:

* The first test runs everywhere. It reads the tracked ``CHECKSUMS.sha256``
  and fails if a requirement has no recorded wheel, which is what would have
  caught the ``httpx`` gap in CI.
* The rest verify the real bytes. They skip, saying so, when the wheels are
  absent - which is the honest state of a clone.
"""

from __future__ import annotations

import email.parser
import hashlib
import re
import struct
import zipfile
from pathlib import Path

import pytest

SOURCE_ROOT = Path(__file__).resolve().parents[2]
WHEELS = SOURCE_ROOT / "installer" / "wheels"
CHECKSUMS = WHEELS / "CHECKSUMS.sha256"
REQUIREMENTS = SOURCE_ROOT / "requirements.txt"


def _normalise(name: str) -> str:
    """PEP 503: compare distribution names case-insensitively, ignoring -._ runs."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _recorded_checksums() -> dict[str, str]:
    """Parse CHECKSUMS.sha256 into {wheel filename: sha256}."""
    if not CHECKSUMS.is_file():
        pytest.fail(
            "installer/wheels/CHECKSUMS.sha256 is missing; it is the only tracked "
            "record of which wheels a release must contain"
        )
    recorded: dict[str, str] = {}
    for line in CHECKSUMS.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        digest, _, name = stripped.partition("  ")
        if not name:
            pytest.fail(f"malformed CHECKSUMS.sha256 line: {line!r}")
        recorded[name.strip()] = digest.strip().lower()
    return recorded


def _top_level_requirements() -> list[str]:
    """The distribution names requirements.txt asks for directly."""
    names = []
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9._-]+)", stripped)
        if match:
            names.append(_normalise(match.group(1)))
    return names


def _wheels_on_disk() -> list[Path]:
    return sorted(WHEELS.glob("*.whl"))


def _require_wheels() -> list[Path]:
    wheels = _wheels_on_disk()
    if not wheels:
        pytest.skip(
            "the offline wheels are gitignored, so a clone carries none of them; "
            "run this where the release was assembled"
        )
    return wheels


def _read_metadata(wheel: Path) -> email.message.Message:
    with zipfile.ZipFile(wheel) as archive:
        members = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
        if not members:
            pytest.fail(f"{wheel.name} has no .dist-info/METADATA")
        return email.parser.Parser().parsestr(
            archive.read(members[0]).decode("utf-8", errors="replace")
        )


def _distribution_of(wheel_name: str) -> str:
    """The distribution a wheel filename declares, PEP 503-normalised."""
    return _normalise(wheel_name.split("-", 1)[0])


# The target the installer actually ships: Windows, CPython 3.14 x64.
_TARGET = {
    "sys_platform": "win32",
    "platform_system": "Windows",
    "os_name": "nt",
    "platform_machine": "AMD64",
    "python_version": "3.14",
    "python_full_version": "3.14.6",
    "implementation_name": "cpython",
    "platform_python_implementation": "CPython",
}


def _evaluate_marker(marker: str, extras: tuple[str, ...]) -> bool:
    """Evaluate a PEP 508 marker for the shipped target.

    Only the shapes these wheels actually use are handled: ``and``/``or``
    joined comparisons. Anything unrecognised fails closed, so a marker we
    cannot read keeps the dependency rather than silently dropping it.
    """

    for or_clause in re.split(r"\s+or\s+", marker):
        satisfied = True
        for clause in re.split(r"\s+and\s+", or_clause):
            match = re.match(
                r"^\s*([a-z_]+)\s*(==|!=|>=|<=|>|<|~=)\s*[\"']([^\"']*)[\"']\s*$",
                clause.strip(),
            )
            if not match:
                return False
            variable, operator, value = match.groups()
            if variable == "extra":
                actual = " ".join(extras)
            else:
                actual = _TARGET.get(variable)
                if actual is None:
                    return False
            if operator == "==" and actual != value:
                satisfied = False
            elif operator == "!=" and actual == value:
                satisfied = False
            elif operator == ">=" and not actual >= value:
                satisfied = False
            elif operator == "<=" and not actual <= value:
                satisfied = False
            elif operator == ">" and not actual > value:
                satisfied = False
            elif operator == "<" and not actual < value:
                satisfied = False
            elif operator == "~=" and not actual.startswith(value.rsplit(".", 1)[0]):
                satisfied = False
            if not satisfied:
                break
        if satisfied:
            return True
    return False


# --- runs everywhere, including a fresh clone -------------------------------


def test_every_top_level_requirement_has_a_recorded_wheel():
    recorded = _recorded_checksums()
    available = {_distribution_of(name) for name in recorded}

    missing = [name for name in _top_level_requirements() if name not in available]
    assert missing == [], (
        "requirements.txt asks for these, but no wheel is recorded in "
        f"CHECKSUMS.sha256: {missing}"
    )


def test_the_recorded_wheels_are_the_wheels_a_release_would_contain():
    """A recorded wheel with no file, or a file with no record, is a release bug."""

    recorded = _recorded_checksums()
    on_disk = {wheel.name for wheel in _wheels_on_disk()}
    if not on_disk:
        pytest.skip(
            "the offline wheels are gitignored, so a clone carries none of them; "
            "run this where the release was assembled"
        )

    assert set(recorded) - on_disk == set(), (
        f"recorded but not on disk: {sorted(set(recorded) - on_disk)}"
    )
    assert on_disk - set(recorded) == set(), (
        f"on disk but not recorded: {sorted(on_disk - set(recorded))}"
    )


# --- verifies the real bytes, where the wheels exist ------------------------


def test_every_wheel_matches_its_recorded_checksum():
    recorded = _recorded_checksums()
    for wheel in _require_wheels():
        digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
        assert digest == recorded.get(wheel.name), (
            f"{wheel.name} does not match CHECKSUMS.sha256; the release would "
            "contain an artifact nobody verified"
        )


def test_every_wheel_filename_agrees_with_its_own_metadata():
    """A wheel renamed to masquerade as another package is the classic swap."""

    for wheel in _require_wheels():
        claimed = _distribution_of(wheel.name)
        declared = _normalise(_read_metadata(wheel).get("Name", ""))
        assert claimed == declared, (
            f"{wheel.name} claims to be {claimed!r} but its METADATA says {declared!r}"
        )


def test_the_whole_dependency_closure_is_covered():
    """requirements.txt plus every transitive dependency, not just the top level.

    ``httpx`` was a top-level miss. ``httpcore`` and ``certifi`` are transitive,
    so a top-level-only check would not have caught those.

    Extras and environment markers are honoured, because the raw closure is
    full of dependencies nobody asked for: ``pillow[test-arrow]`` pulls in
    ``pyarrow``, ``fastapi[standard]`` pulls in ``fastar``, and ``uvicorn``
    offers ``uvloop`` only off Windows. Following those blindly would report
    dozens of phantom gaps and drown the real ones.
    """

    wheels = _require_wheels()
    provided: dict[str, email.message.Message] = {}
    for wheel in wheels:
        metadata = _read_metadata(wheel)
        provided[_normalise(metadata.get("Name", ""))] = metadata

    queue = [(name, ()) for name in _top_level_requirements()]
    seen = set()
    missing = []
    while queue:
        name, extras = queue.pop(0)
        if (name, extras) in seen:
            continue
        seen.add((name, extras))

        if name not in provided:
            missing.append(name)
            continue

        for raw in provided[name].get_all("Requires-Dist", []) or []:
            requirement, _, marker = raw.partition(";")
            match = re.match(r"^\s*([A-Za-z0-9._-]+)\s*(\[[^\]]*\])?", requirement)
            if not match:
                continue
            dependency = _normalise(match.group(1))
            wanted = tuple(
                part.strip() for part in (match.group(2) or "").strip("[]").split(",")
                if part.strip()
            )
            # ``extra`` in a Requires-Dist marker names an extra of the package
            # being depended on - the parent - not of this dependency. Passing
            # the child's own extras here would let fastapi[standard] drag in
            # fastapi-cli even though requirements.txt asked for plain fastapi.
            if marker.strip() and not _evaluate_marker(marker.strip(), extras):
                continue
            queue.append((dependency, tuple(dict.fromkeys(extras + wanted))))

    assert missing == [], (
        "the offline wheel set cannot install requirements.txt; these "
        f"distributions have no wheel: {sorted(set(missing))}"
    )


# --- no byte of a wheel may sit outside its own ZIP structure ----------------

_EOCD = b"PK\x05\x06"
_CENTRAL = b"PK\x01\x02"
_LOCAL = b"PK\x03\x04"
_DESCRIPTOR = b"PK\x07\x08"


def _unaccounted_zip_bytes(path: Path) -> list[str]:
    """Every byte of a wheel must sit inside its own ZIP structure.

    REA flagged this gap itself: its inventory, like ``zipfile``, lists
    central-directory entries only, so a ZIP comment after the
    End-Of-Central-Directory record, bytes prepended before the first local
    header, and space between members are invisible to both. Nothing here
    looked, and these wheels are installed by a one-click Server setup that
    runs elevated on a customer machine.

    Returns one finding per region that no member accounts for.
    """

    data = path.read_bytes()
    findings: list[str] = []
    name = path.name

    eocd = data.rfind(_EOCD)
    if eocd < 0:
        return [f"{name}: no End-Of-Central-Directory record"]
    if len(data) < eocd + 22:
        return [f"{name}: truncated End-Of-Central-Directory record"]
    try:
        (_disk, _cd_disk, _recs, total, cd_size, cd_off,
         comment_len) = struct.unpack("<HHHHIIH", data[eocd + 4:eocd + 22])
    except struct.error:
        return [f"{name}: unreadable End-Of-Central-Directory record"]

    if comment_len:
        findings.append(f"{name}: a {comment_len}-byte ZIP comment follows the central directory")

    # A plain archive begins with its first local header, so this is checkable
    # before anything else and survives a central directory that will not walk.
    if data[:4] != _LOCAL:
        findings.append(f"{name}: the archive does not begin with a local file header, so bytes were prepended to it")

    # Walk the central directory. Where the walk ends must be where the record
    # says a cd_size-byte central directory ends.
    pos = cd_off
    entries = []
    for _ in range(total):
        if data[pos:pos + 4] != _CENTRAL:
            findings.append(f"{name}: bad central-directory signature at byte {pos}")
            break
        if len(data) < pos + 46:
            findings.append(f"{name}: truncated central-directory header at byte {pos}")
            break
        try:
            (_made, _need, flags, _method, _mtime, _mdate, _crc, csize, _usize,
             nlen, elen, clen, _disk_no, _iattr, _eattr, lho) = struct.unpack(
                "<HHHHHHIIIHHHHHII", data[pos + 4:pos + 46])
        except struct.error:
            findings.append(f"{name}: unreadable central-directory header at byte {pos}")
            break
        entries.append({"lho": lho, "csize": csize, "flags": flags})
        pos += 46 + nlen + elen + clen
    if pos != cd_off + cd_size:
        findings.append(
            f"{name}: the central directory occupies {pos - cd_off} bytes but its "
            f"record claims {cd_size}"
        )

    # Walk the local headers in offset order and account for the space between.
    ends = []
    for entry in sorted(entries, key=lambda e: e["lho"]):
        lho = entry["lho"]
        if data[lho:lho + 4] != _LOCAL:
            findings.append(f"{name}: bad local header signature at byte {lho}")
            continue
        if len(data) < lho + 30:
            findings.append(f"{name}: truncated local header at byte {lho}")
            continue
        try:
            (_ver, _flags, _method, _mtime, _mdate, _crc, _lcsize, _lusize,
             nlen, elen) = struct.unpack("<HHHHHIIIHH", data[lho + 4:lho + 30])
        except struct.error:
            findings.append(f"{name}: unreadable local header at byte {lho}")
            continue
        end = lho + 30 + nlen + elen + entry["csize"]
        if entry["flags"] & 0x08:
            # A data descriptor trails the data only when bit 3 is set: an
            # optional signature, then crc, compressed size and uncompressed
            # size. Stepping over the central directory's csize already
            # crossed the data, so only the descriptor itself is left.
            end += 16 if data[end:end + 4] == _DESCRIPTOR else 12
        ends.append((lho, end))

    if ends:
        if ends[0][0]:
            findings.append(f"{name}: {ends[0][0]} bytes precede the first local header")
        for before, after in zip(ends, ends[1:]):
            gap = after[0] - before[1]
            if gap:
                findings.append(
                    f"{name}: {gap} bytes between the member ending at {before[1]} "
                    f"and the next local header at {after[0]}"
                )
        if cd_off != ends[-1][1]:
            findings.append(
                f"{name}: {cd_off - ends[-1][1]} bytes between the last member "
                f"and the central directory"
            )

    if eocd + 22 + comment_len != len(data):
        findings.append(
            f"{name}: {len(data) - (eocd + 22 + comment_len)} bytes follow the "
            f"End-Of-Central-Directory record"
        )

    return findings


def test_no_wheel_carries_bytes_outside_its_own_zip_structure():
    """A wheel that installs nothing extra is not a wheel that carries nothing
    extra, and the difference is invisible to every ZIP reader."""

    for wheel in _require_wheels():
        findings = _unaccounted_zip_bytes(wheel)
        assert findings == [], (
            "these bytes belong to no member of the archive, so no ZIP reader "
            "and no inventory built from one would ever list them: "
            + "; ".join(findings)
        )
