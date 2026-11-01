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
