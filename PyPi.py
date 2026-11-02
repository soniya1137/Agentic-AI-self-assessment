#!/usr/bin/env python3
"""
"""
import json
import sys
import urllib.error
import urllib.request

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version

TARGET = "3.11"
PYPI = "https://pypi.org/pypi"


def fetch(url):
    """Return parsed JSON, or None on HTTP 404."""
    req = urllib.request.Request(url, headers={"User-Agent": "req-checker/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def pinned_version(req):
    """Return the exact version if the line pins one with == (or ===), else None."""
    for spec in req.specifier:
        if spec.operator in ("==", "===") and not spec.version.endswith(".*"):
            return spec.version
    return None


def min_python(requires_python):
    """Highest lower bound found in a requires_python string, e.g. '>=3.8,<4' -> 3.8."""
    try:
        spec_set = SpecifierSet(requires_python)
    except InvalidSpecifier:
        return None
    bounds = [
        Version(s.version.rstrip(".*"))
        for s in spec_set
        if s.operator in (">=", ">", "~=", "==", "===")
    ]
    return max(bounds) if bounds else None


def main(path):
    with open(path, encoding="utf-8") as f:
        lines = [l.split(" #")[0].strip() for l in f]
    # skip blanks, comments and pip options (-r, -e, --index-url ...)
    lines = [l for l in lines if l and not l.startswith(("#", "-"))]

    not_found, incompatible = [], []
    highest, highest_min = None, None

    for line in lines:
        try:
            req = Requirement(line)
        except InvalidRequirement:
            print(f"warning: cannot parse line: {line!r}", file=sys.stderr)
            not_found.append(line)
            continue

        version = pinned_version(req)
        if version:
            data = fetch(f"{PYPI}/{req.name}/{version}/json")
        else:
            data = fetch(f"{PYPI}/{req.name}/json")  # unpinned -> latest release

        if data is None:  # package or pinned version does not exist
            not_found.append(f"{req.name}=={version}" if version else req.name)
            continue

        version = version or data["info"]["version"]
        label = f"{req.name}=={version}"
        rp = data["info"].get("requires_python")
        if not rp:
            continue

        try:
            if not SpecifierSet(rp).contains(TARGET, prereleases=True):
                incompatible.append(f"{label} (requires {rp})")
        except InvalidSpecifier:
            pass

        m = min_python(rp)
        if m is not None and (highest_min is None or m > highest_min):
            highest, highest_min = label, m

    print(f"1. dependencies checked: {len(lines)}")
    print(f"2. not found on pypi: {len(not_found)}")
    for n in not_found:
        print(f"     {n}")
    print(f"3. incompatible with python {TARGET}: {len(incompatible)}")
    for n in incompatible:
        print(f"     {n}")
    print(f"4. highest requirement: {highest or 'n/a'}"
          + (f"  (python >={highest_min})" if highest else ""))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "requirements.txt")
    