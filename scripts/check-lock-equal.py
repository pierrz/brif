#!/usr/bin/env python3
# pylint: disable=invalid-name  # the file name is kebab-case, like the other scripts
"""
Proof for INFRA-236 (Poetry -> uv): the move changes the tool and nothing else, so every package
that uv installs must have exactly the version that Poetry locked.

    python3 scripts/check-lock-equal.py                    compare, print every difference
    python3 scripts/check-lock-equal.py --constraints      print the constraint-dependencies block
    python3 scripts/check-lock-equal.py --old-lock FILE    compare with another poetry.lock

What it compares, as sets of (name, version), names normalised as in PEP 503:
- 'uv export --frozen --no-hashes --all-groups' (what uv.lock installs, dev tools included), and
- the app/poetry.lock of the last commit before the migration (OLD_REV, read with 'git show').
The git dependency (starlette-core) has no version in the export: its version is read from
app/uv.lock, and its commit is compared with 'resolved_reference' of the old lock.

It also checks that [tool.uv] constraint-dependencies of app/pyproject.toml is exactly the list
derived from the old lock.

Exit code 0 and 'EQUAL' when there is no difference, 1 otherwise. Needs Python 3.11+ (tomllib) and
uv on the PATH. This is a migration proof: delete it once the dependencies move on (INFRA-227).
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    sys.exit(
        "Python 3.11+ is needed (tomllib). From anywhere: uv run --no-project --python 3.12 "
        "scripts/check-lock-equal.py"
    )

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "app"
# a commit of main that still has app/poetry.lock (INFRA-235, before this migration)
OLD_REV = "2c82c6f"


def norm(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def read_old_lock(path):
    """Return ({name: version}, {name: git commit}, {name: name as written in the lock})."""
    if path:
        text = Path(path).read_text(encoding="utf-8")
    else:
        done = subprocess.run(
            ["git", "-C", str(REPO), "show", f"{OLD_REV}:app/poetry.lock"],
            capture_output=True,
            text=True,
            check=False,
        )
        if done.returncode:
            sys.exit(
                f"cannot read app/poetry.lock at {OLD_REV} ({done.stderr.strip()}); "
                "fetch the history or pass --old-lock FILE"
            )
        text = done.stdout
    versions, commits, written = {}, {}, {}
    for package in tomllib.loads(text)["package"]:
        key = norm(package["name"])
        versions[key] = package["version"]
        written[key] = package["name"]
        source = package.get("source", {})
        if source.get("type") == "git":
            commits[key] = source["resolved_reference"]
    return versions, commits, written


def read_uv_lock():
    """Return ({name: version}, {name: git commit}) of app/uv.lock."""
    data = tomllib.loads((APP / "uv.lock").read_text(encoding="utf-8"))
    versions, commits = {}, {}
    for package in data["package"]:
        key = norm(package["name"])
        if "version" in package:
            versions[key] = package["version"]
        git = package.get("source", {}).get("git")
        if git:
            commits[key] = git.split("#")[-1]
    return versions, commits


def read_export():
    """Return the set of (name, version) of 'uv export', and {name: git commit}."""
    done = subprocess.run(
        [
            "uv",
            "export",
            "--frozen",
            "--no-hashes",
            "--all-groups",
            "--no-emit-project",
            "--project",
            str(APP),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode:
        sys.exit(f"uv export failed: {done.stderr.strip()}")
    lock_versions, _ = read_uv_lock()
    packages, commits = set(), {}
    for raw in done.stdout.splitlines():
        line = raw.split(" #")[0].strip()
        if not line or line.startswith("#"):
            continue
        requirement = line.split(";")[0].strip()
        if "==" in requirement:
            name, version = requirement.split("==")
            packages.add((norm(name), version))
        elif " @ git+" in requirement:
            name, url = requirement.split(" @ ", 1)
            packages.add((norm(name), lock_versions[norm(name)]))
            commits[norm(name)] = url.rsplit("@", 1)[1]
        else:
            sys.exit(f"unexpected line in the export: {line}")
    return packages, commits


def constraints_from(versions, written):
    return [f"{written[key]}=={versions[key]}" for key in sorted(versions)]


def read_pyproject_constraints():
    data = tomllib.loads((APP / "pyproject.toml").read_text(encoding="utf-8"))
    return data.get("tool", {}).get("uv", {}).get("constraint-dependencies", [])


def package_differences(old_versions, old_commits, new, new_commits):
    """Differences between the old lock and the uv export, one line each."""
    old = set(old_versions.items())
    new_names = {name for name, _ in new}
    lines = []
    for name, version in sorted(old - new):
        if name in new_names:
            seen = ", ".join(sorted(v for n, v in new if n == name))
            lines.append(f"version differs: {name} old {version}, uv {seen}")
        else:
            lines.append(
                f"only in the old lock (uv does not install it): {name}=={version}"
            )
    for name, version in sorted(new - old):
        if name not in old_versions:
            lines.append(
                f"only in uv (the old lock has no such package): {name}=={version}"
            )
    for name in sorted(set(old_commits) | set(new_commits)):
        if old_commits.get(name) != new_commits.get(name):
            lines.append(
                f"git commit differs: {name} old {old_commits.get(name)}, "
                f"uv {new_commits.get(name)}"
            )
    return lines


def constraint_differences(derived, declared):
    """Differences between the constraint list derived from the old lock and the one in pyproject."""
    lines = [
        f"constraint-dependencies lacks: {line}"
        for line in sorted(set(derived) - set(declared))
    ]
    lines += [
        f"constraint-dependencies has a line the old lock does not: {line}"
        for line in sorted(set(declared) - set(derived))
    ]
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", maxsplit=1)[0])
    parser.add_argument(
        "--old-lock", help="a poetry.lock file (default: the one of OLD_REV)"
    )
    parser.add_argument(
        "--constraints",
        action="store_true",
        help="print the constraint-dependencies lines derived from the old lock and stop",
    )
    args = parser.parse_args()

    old_versions, old_commits, written = read_old_lock(args.old_lock)
    derived = constraints_from(old_versions, written)
    if args.constraints:
        print("constraint-dependencies = [")
        for line in derived:
            print(f'    "{line}",')
        print("]")
        return 0

    new, new_commits = read_export()
    differences = package_differences(old_versions, old_commits, new, new_commits)
    differences += constraint_differences(derived, read_pyproject_constraints())

    for line in differences:
        print(line)
    print(
        f"old lock: {len(old_versions)} packages; uv export (all groups): {len(new)} packages; "
        f"differences: {len(differences)}"
    )
    print("EQUAL" if not differences else "DIFFERENT")
    return 1 if differences else 0


if __name__ == "__main__":
    sys.exit(main())
