#!/usr/bin/env python3
"""Detect Entity Framework flavour, versions, providers and target frameworks per project.

Usage: python3 detect_ef.py <repo-root> [--json]
No third-party dependencies. Reads .csproj, packages.config, Directory.Packages.props.
"""
import json
import os
import re
import sys
from pathlib import Path

SKIP_DIRS = {"bin", "obj", "node_modules", ".git", ".vs", "packages", ".idea", "TestResults"}

# Support status as of Nov 2026 (see references/upgrade-readiness.md)
CORE_SUPPORT = {
    11: ("supported", "STS, needs .NET 11"),
    10: ("supported", "LTS until Nov 10 2028, needs .NET 10"),
    9: ("ended", "support ended Nov 10 2026"),
    8: ("ended", "support ended Nov 10 2026"),
}

PROVIDER_MAP = {
    "Microsoft.EntityFrameworkCore.SqlServer": "SqlServer",
    "Microsoft.EntityFrameworkCore.Sqlite": "Sqlite",
    "Microsoft.EntityFrameworkCore.InMemory": "InMemory",
    "Microsoft.EntityFrameworkCore.Cosmos": "Cosmos",
    "Npgsql.EntityFrameworkCore.PostgreSQL": "PostgreSQL",
    "Pomelo.EntityFrameworkCore.MySql": "MySql",
    "MySql.EntityFrameworkCore": "MySql",
    "Oracle.EntityFrameworkCore": "Oracle",
}

TEST_PKGS = ("xunit", "nunit", "mstest", "microsoft.net.test.sdk")


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            yield Path(dirpath) / f


def read(p):
    try:
        return Path(p).read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


def parse_version(v):
    if not v:
        return None, None
    v = v.strip().strip("[]()").split(",")[0]
    m = re.match(r"(\d+)(?:\.(\d+))?", v)
    if not m:
        return v, None
    return v, int(m.group(1))


def package_refs(text):
    """Return {package: version} from PackageReference / PackageVersion (attribute or child element)."""
    refs = {}
    for m in re.finditer(r"<Package(?:Reference|Version)\b([^>]*?)(/>|>(.*?)</Package(?:Reference|Version)>)", text, re.S | re.I):
        attrs, body = m.group(1), m.group(3) or ""
        name = re.search(r'\b(?:Include|Update)\s*=\s*"([^"]+)"', attrs)
        if not name:
            continue
        ver = re.search(r'\bVersion(?:Override)?\s*=\s*"([^"]+)"', attrs)
        if not ver:
            ver = re.search(r"<Version>([^<]+)</Version>", body)
        refs[name.group(1)] = ver.group(1) if ver else None
    return refs


def old_style_refs(text):
    """<Reference Include="EntityFramework, Version=6.0.0.0, ..."> (non-SDK projects)."""
    refs = {}
    for m in re.finditer(r'<Reference\s+Include="(EntityFramework[\w.]*)\s*,\s*Version=([\d.]+)', text):
        refs[m.group(1)] = m.group(2)
    return refs


def packages_config(path):
    refs = {}
    for m in re.finditer(r'<package\s+id="([^"]+)"\s+version="([^"]+)"', read(path)):
        refs[m.group(1)] = m.group(2)
    return refs


def find_cpm(proj_dir, root):
    """Find nearest Directory.Packages.props going up to root."""
    d = Path(proj_dir).resolve()
    root = Path(root).resolve()
    while True:
        cand = d / "Directory.Packages.props"
        if cand.exists():
            return package_refs(read(cand))
        if d == root or d.parent == d:
            return {}
        d = d.parent


def analyse_project(csproj, root):
    text = read(csproj)
    proj_dir = csproj.parent
    refs = package_refs(text)
    refs.update(old_style_refs(text))
    pc = proj_dir / "packages.config"
    if pc.exists():
        refs.update(packages_config(pc))
    cpm = find_cpm(proj_dir, root)
    for k, v in list(refs.items()):
        if v is None and k in cpm:
            refs[k] = cpm[k]

    tfms = re.findall(r"<TargetFrameworks?>([^<]+)</TargetFrameworks?>", text)
    tfms = [t.strip() for x in tfms for t in x.split(";") if t.strip()]
    fx = re.search(r"<TargetFrameworkVersion>v?([\d.]+)</TargetFrameworkVersion>", text)
    if fx:
        tfms.append("net" + fx.group(1).replace(".", ""))

    ef_core = {k: v for k, v in refs.items() if k.lower().startswith("microsoft.entityframeworkcore")}
    ef6 = {k: v for k, v in refs.items() if k == "EntityFramework" or k.startswith("EntityFramework.")}
    providers = sorted({PROVIDER_MAP[k] for k in refs if k in PROVIDER_MAP})
    if ef6 and not providers:
        providers = ["SqlServer (EF6 default)"]
    is_test = any(k.lower().startswith(TEST_PKGS) for k in refs) or bool(re.search(r"test", csproj.stem, re.I))

    info = {
        "project": csproj.stem,
        "path": str(csproj.relative_to(root)),
        "dir": str(proj_dir.relative_to(root)) if proj_dir != Path(root) else ".",
        "target_frameworks": tfms,
        "is_test": is_test,
        "providers": providers,
        "flavour": None,
        "ef_version": None,
        "ef_major": None,
        "support": None,
        "support_note": None,
        "packages": {**ef_core, **ef6},
        "warnings": [],
    }

    if ef_core:
        main = ef_core.get("Microsoft.EntityFrameworkCore") or next((v for v in ef_core.values() if v), None)
        ver, major = parse_version(main)
        info.update(flavour="EF Core", ef_version=ver, ef_major=major)
        majors = {parse_version(v)[1] for v in ef_core.values() if v}
        majors.discard(None)
        if len(majors) > 1:
            info["warnings"].append(f"EF810 mixed EF Core major versions in one project: {sorted(majors)}")
        if major is not None:
            status, note = CORE_SUPPORT.get(major, ("ended" if major < 8 else "unknown", "out of support" if major < 8 else "newer than known"))
            info.update(support=status, support_note=note)
    elif ef6:
        ver, major = parse_version(ef6.get("EntityFramework") or next(iter(ef6.values())))
        info.update(flavour="EF6", ef_version=ver, ef_major=major, support="maintenance",
                    support_note="EF6 is maintenance only; latest 6.5.x")

    if any(re.match(r"net4\d", t) for t in tfms) and info["flavour"] == "EF Core" and (info["ef_major"] or 0) >= 5:
        info["warnings"].append("EF Core 5+ does not support .NET Framework targets")
    if "EFOptimizeContext" in text:
        info["warnings"].append("EF805 EFOptimizeContext MSBuild property present (removed in EF Core 11)")
    return info


def detect(root):
    root = Path(root).resolve()
    projects = [analyse_project(p, root) for p in walk(root) if p.suffix == ".csproj"]
    edmx = [str(p.relative_to(root)) for p in walk(root) if p.suffix == ".edmx"]
    ef_projects = [p for p in projects if p["flavour"]]
    majors = {(p["flavour"], p["ef_major"]) for p in ef_projects if not p["is_test"]}
    summary = {
        "root": str(root),
        "projects_total": len(projects),
        "ef_projects": len(ef_projects),
        "edmx_files": edmx,
        "versions_in_use": sorted(f"{f} {m}" for f, m in majors),
        "solution_warnings": [],
    }
    core_majors = {m for f, m in majors if f == "EF Core" and m}
    if len(core_majors) > 1:
        summary["solution_warnings"].append(f"EF810 different EF Core majors across projects: {sorted(core_majors)}; align with Central Package Management")
    return {"summary": summary, "projects": projects}


def primary(result):
    """Pick the dominant non-test EF flavour/major for the solution."""
    eps = [p for p in result["projects"] if p["flavour"] and not p["is_test"]] or [p for p in result["projects"] if p["flavour"]]
    if not eps:
        return None, None
    best = max(eps, key=lambda p: (p["flavour"] == "EF Core", p["ef_major"] or 0))
    return best["flavour"], best["ef_major"]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    res = detect(sys.argv[1])
    if "--json" in sys.argv:
        print(json.dumps(res, indent=2))
        return
    s = res["summary"]
    print(f"Root: {s['root']}")
    print(f"Projects: {s['projects_total']}  with EF: {s['ef_projects']}  EDMX: {len(s['edmx_files'])}")
    for p in res["projects"]:
        if not p["flavour"]:
            continue
        tag = " [test]" if p["is_test"] else ""
        print(f"- {p['project']}{tag}: {p['flavour']} {p['ef_version']} | {','.join(p['target_frameworks']) or '?'} | "
              f"providers: {','.join(p['providers']) or '?'} | support: {p['support']} ({p['support_note']})")
        for w in p["warnings"]:
            print(f"    ! {w}")
    for w in s["solution_warnings"]:
        print(f"! {w}")
    if s["edmx_files"]:
        print("! EDMX found (EF6 designer):", ", ".join(s["edmx_files"]))


if __name__ == "__main__":
    main()
