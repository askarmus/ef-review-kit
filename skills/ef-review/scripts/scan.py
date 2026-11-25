#!/usr/bin/env python3
"""EF review scanner: finds CANDIDATE issues in Entity Framework code (EF6 + EF Core).

It is heuristic (regex + brace matching, no Roslyn). Every hit must be verified by
reading the code. Rule details: ../references/*.md

Usage:
  python3 scan.py <repo-root> [--format json|md] [--out FILE]
                  [--ef-version N] [--target-version N] [--include-tests] [--max-per-rule N]
No third-party dependencies.
"""
import argparse
import bisect
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import detect_ef  # noqa: E402

SKIP_DIRS = detect_ef.SKIP_DIRS
WEIGHTS = {"critical": 10, "high": 5, "medium": 2, "low": 0.5, "info": 0}
SEV_ORDER = ["critical", "high", "medium", "low", "info"]

# id: (category, severity, title, reference, min EF Core major or None, core_only)
RULES = {
    "EF001": ("wrong-usage", "high", "Query inside a loop (N+1)", "antipatterns.md", None, False),
    "EF002": ("wrong-usage", "high", "Materialised before filtering (client-side evaluation)", "antipatterns.md", None, False),
    "EF003": ("wrong-usage", "medium", "Count() > 0 instead of Any()", "antipatterns.md", None, False),
    "EF004": ("wrong-usage", "high", "SaveChanges inside a loop", "antipatterns.md", None, False),
    "EF005": ("security", "critical", "Raw SQL built with concatenation/interpolation (SQL injection)", "security.md", None, False),
    "EF006": ("wrong-usage", "high", "Blocking on async EF call (.Result/.Wait/GetResult)", "antipatterns.md", None, False),
    "EF007": ("wrong-usage", "medium", "Sync EF call inside async method", "antipatterns.md", None, False),
    "EF008": ("wrong-usage", "critical", "DbContext with singleton/static lifetime", "antipatterns.md", None, False),
    "EF009": ("slow-query", "medium", "Multiple Includes without AsSplitQuery (cartesian explosion risk)", "antipatterns.md", 5, True),
    "EF010": ("slow-query", "medium", "Read-only query without AsNoTracking", "antipatterns.md", None, False),
    "EF011": ("modernise", "medium", "Load-then-delete; use ExecuteDelete", "antipatterns.md", 7, True),
    "EF012": ("modernise", "medium", "Load-modify-save loop; use ExecuteUpdate", "antipatterns.md", 7, True),
    "EF013": ("slow-query", "high", "Unbounded full-table load", "antipatterns.md", None, False),
    "EF014": ("slow-query", "low", "Contains() over an in-memory list (large IN / OPENJSON)", "antipatterns.md", None, False),
    "EF015": ("slow-query", "medium", "Non-sargable predicate (function on column)", "antipatterns.md", None, False),
    "EF016": ("wrong-usage", "low", "Include ignored because the query projects with Select", "antipatterns.md", None, True),
    "EF017": ("slow-query", "medium", "Lazy loading enabled (hidden N+1)", "antipatterns.md", None, False),
    "EF018": ("wrong-usage", "critical", "Parallel operations on one DbContext", "antipatterns.md", None, False),
    "EF101": ("model", "medium", "decimal property without precision", "model-config.md", None, False),
    "EF102": ("model", "low", "string properties without max length (nvarchar(max))", "model-config.md", None, False),
    "EF103": ("model", "high", "Cascade delete configured: review blast radius", "model-config.md", None, False),
    "EF104": ("model", "medium", "No concurrency tokens anywhere", "model-config.md", None, False),
    "EF105": ("modernise", "info", "Owned types: consider complex types", "model-config.md", 8, True),
    "EF201": ("migrations", "critical", "Destructive migration operation", "migrations.md", None, False),
    "EF202": ("migrations", "high", "Rename in migration (rolling deploy / raw SQL break risk)", "migrations.md", None, False),
    "EF203": ("migrations", "medium", "AlterColumn in migration (data/lock risk)", "migrations.md", None, False),
    "EF204": ("migrations", "low", "Raw SQL in migration", "migrations.md", None, False),
    "EF205": ("migrations", "medium", "Database.Migrate() at app startup", "migrations.md", None, True),
    "EF206": ("migrations", "high", "EnsureCreated in application code", "migrations.md", None, True),
    "EF301": ("integrity", "medium", "Multiple SaveChanges without a transaction", "data-integrity.md", None, False),
    "EF302": ("integrity", "medium", "Concurrency token present but DbUpdateConcurrencyException never handled", "data-integrity.md", None, False),
    "EF303": ("integrity", "low", "No retry strategy for transient SQL errors", "data-integrity.md", None, False),
    "EF401": ("security", "high", "EnableSensitiveDataLogging not limited to development", "security.md", None, True),
    "EF402": ("security", "critical", "Connection string with password in code/config", "security.md", None, False),
    "EF403": ("security", "medium", "IgnoreQueryFilters: check tenant/soft-delete leak", "security.md", None, True),
    "EF404": ("security", "low", "EnableDetailedErrors not limited to development", "security.md", None, True),
    "EF502": ("memory", "high", "DbContext injected into a long-lived hosted service", "memory-connections.md", None, True),
    "EF503": ("memory", "info", "Consider DbContext pooling", "memory-connections.md", None, True),
    "EF504": ("memory", "low", "ToAsyncEnumerable on EF query; use AsAsyncEnumerable", "memory-connections.md", None, True),
    "EF505": ("memory", "medium", "DbContext created with new and maybe not disposed", "memory-connections.md", None, False),
    "EF601": ("architecture", "info", "Generic repository over DbContext", "architecture-testing-observability.md", None, False),
    "EF602": ("architecture", "info", "IQueryable returned from public method", "architecture-testing-observability.md", None, False),
    "EF603": ("testing", "medium", "InMemory provider used for tests", "architecture-testing-observability.md", None, True),
    "EF604": ("observability", "info", "No query tags (TagWith) anywhere", "architecture-testing-observability.md", None, True),
    "EF605": ("observability", "info", "No SQL logging / slow query interceptor found", "architecture-testing-observability.md", None, False),
    "EF701": ("modernise", "info", "Left join via GroupJoin/DefaultIfEmpty; use LeftJoin", "features-by-version.md", 10, True),
    "EF702": ("modernise", "info", "OrderBy(...).First(); consider MaxBy/MinBy", "features-by-version.md", 11, True),
    "EF705": ("modernise", "info", "Combined query filter; consider named filters", "features-by-version.md", 10, True),
    "EF706": ("modernise", "info", "Full join emulated with Union/Concat; use FullJoin", "features-by-version.md", 11, True),
    "EF801": ("upgrade", "high", "EF version out of support", "upgrade-readiness.md", None, False),
    "EF802": ("upgrade", "info", "Target framework blocks EF Core upgrade", "upgrade-readiness.md", None, False),
    "EF803": ("upgrade", "medium", "UseSqlServer without explicit compatibility level (EF 11 default changes to 160)", "upgrade-readiness.md", None, True),
    "EF804": ("upgrade", "high", "Entra ID / Azure AD auth: needs separate package on EF 11 (SqlClient 7)", "upgrade-readiness.md", None, False),
    "EF805": ("upgrade", "medium", "EFOptimizeContext MSBuild property removed in EF 11", "upgrade-readiness.md", None, True),
    "EF806": ("upgrade", "high", "Cosmos provider: serializer and __jObject breaking changes in EF 11", "upgrade-readiness.md", None, True),
    "EF807": ("upgrade", "medium", "Migrate() throws on pending model changes from EF 9", "upgrade-readiness.md", None, True),
    "EF808": ("upgrade", "info", "Contains translation changes in EF 10 (multiple parameters)", "upgrade-readiness.md", None, False),
    "EF809": ("upgrade", "info", "EF6 to EF Core migration readiness item", "upgrade-readiness.md", None, False),
    "EF810": ("upgrade", "medium", "Mixed EF package versions", "upgrade-readiness.md", None, False),
}

MATERIALISERS = (r"ToList|ToListAsync|ToArray|ToArrayAsync|First|FirstOrDefault|FirstAsync|FirstOrDefaultAsync|"
                 r"Single|SingleOrDefault|SingleAsync|SingleOrDefaultAsync|Find|FindAsync|Any|AnyAsync|All|AllAsync|"
                 r"Count|CountAsync|LongCount|LongCountAsync|Sum|SumAsync|Max|MaxAsync|Min|MinAsync|Average|AverageAsync|"
                 r"ToDictionary|ToDictionaryAsync|Load|LoadAsync|ToHashSet|ToHashSetAsync|Last|LastOrDefault|LastAsync|LastOrDefaultAsync")
SYNC_MAT = r"ToList|ToArray|First|FirstOrDefault|Single|SingleOrDefault|Find|Any|Count|LongCount|Sum|Max|Min|Average|ToDictionary|Load|SaveChanges|Last|LastOrDefault|ToHashSet"
DEFAULT_CTX_NAMES = ["_context", "context", "_db", "db", "_dbContext", "dbContext", "_dbcontext", "ctx", "_ctx",
                     "_dataContext", "dataContext", "_entities", "entities", "_appDbContext", "appDbContext"]
NOT_CTX_TYPES = {"HttpContext", "SynchronizationContext", "ExecutionContext", "ValidationContext", "SecurityContext",
                 "ActionContext", "FilterContext", "ModelBindingContext", "OperationContext", "CallContext",
                 "TestContext", "HubCallerContext", "AuthorizationHandlerContext", "ResourceExecutingContext",
                 "ActionExecutingContext", "ExceptionContext", "ControllerContext", "ViewContext", "PageContext",
                 "StreamingContext", "JsonSerializerContext", "AssemblyLoadContext", "ObjectContext", "DbContext"}
METHOD_RE = re.compile(
    r"(?:(?:public|private|protected|internal|static|async|override|virtual|sealed|new|extern|unsafe|partial)\s+)+"
    r"(?!class\b|interface\b|record\b|struct\b|enum\b)([\w<>\[\],.?]+(?:\s*<[^;{()]*>)?)\s+(\w+)\s*(?:<[^>(]*>)?\s*\(([^;{]*?)\)\s*(?:where\s[^{;]*)?\{")
LOOP_RE = re.compile(r"\b(foreach|for|while)\s*\(|\.\s*ForEach\s*\(|Parallel\s*\.\s*ForEach(?:Async)?\s*\(")
SECRET_PLACEHOLDER = re.compile(r"^\s*(\$\{|#\{|__|<|\{\{|\*+|x+|your|changeme|password)\s*", re.I)


# ----------------------------------------------------------------------------- text utils

def blank(arr, a, b):
    for k in range(a, min(b, len(arr))):
        if arr[k] != "\n":
            arr[k] = " "


def strip_code(text):
    """Return (clean, skel): clean = comments blanked; skel = comments + string/char contents blanked.
    Same length as text so offsets line up."""
    n = len(text)
    clean, skel = list(text), list(text)
    i = 0
    while i < n:
        c = text[i]
        nx = text[i + 1] if i + 1 < n else ""
        if c == "/" and nx == "/":
            j = text.find("\n", i)
            j = n if j == -1 else j
            blank(clean, i, j); blank(skel, i, j); i = j; continue
        if c == "/" and nx == "*":
            j = text.find("*/", i + 2)
            j = n if j == -1 else j + 2
            blank(clean, i, j); blank(skel, i, j); i = j; continue
        if text.startswith('"""', i):
            j = text.find('"""', i + 3)
            j = n if j == -1 else j + 3
            blank(skel, i + 3, j - 3); i = j; continue
        if c == '"':
            verbatim = text[max(0, i - 2):i].count("@") > 0
            j = i + 1
            while j < n:
                ch = text[j]
                if verbatim:
                    if ch == '"':
                        if j + 1 < n and text[j + 1] == '"':
                            j += 2; continue
                        break
                else:
                    if ch == "\\":
                        j += 2; continue
                    if ch == '"' or ch == "\n":
                        break
                j += 1
            blank(skel, i + 1, j); i = j + 1; continue
        if c == "'":
            j = i + 1
            if j < n and text[j] == "\\":
                j += 2
            k = text.find("'", j, j + 8)
            if k != -1:
                blank(skel, i + 1, k); i = k + 1; continue
        i += 1
    return "".join(clean), "".join(skel)


def match_close(s, open_idx):
    o, c = s[open_idx], {"(": ")", "{": "}", "[": "]"}[s[open_idx]]
    depth = 0
    for k in range(open_idx, len(s)):
        if s[k] == o:
            depth += 1
        elif s[k] == c:
            depth -= 1
            if depth == 0:
                return k
    return len(s) - 1


def statement_span(skel, off, lo=0, hi=None):
    hi = len(skel) if hi is None else hi
    depth, i = 0, off - 1
    while i >= lo:
        ch = skel[i]
        if ch == "}" and depth == 0:
            break  # end of a previous block: statement starts after it
        if ch in ")}]":
            depth += 1
        elif ch in "({[":
            if depth == 0:
                break
            depth -= 1
        elif ch == ";" and depth == 0:
            break
        i -= 1
    start = i + 1
    while start < off and skel[start].isspace():
        start += 1
    depth, j = 0, off
    while j < hi:
        ch = skel[j]
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            if depth == 0:
                break
            depth -= 1
        elif ch == ";" and depth == 0:
            j += 1
            break
        j += 1
    return start, j


# ----------------------------------------------------------------------------- file model

class SrcFile:
    def __init__(self, path, rel, text):
        self.path, self.rel, self.text = path, rel, text
        self.clean, self.skel = strip_code(text)
        self.nl = [i for i, ch in enumerate(text) if ch == "\n"]
        self.methods = self._methods()
        self.loops = self._loops()

    def line(self, off):
        return bisect.bisect_left(self.nl, off) + 1

    def snippet(self, off, max_len=160):
        ln = self.line(off)
        lines = self.text.splitlines()
        s = lines[ln - 1].strip() if 0 < ln <= len(lines) else ""
        return s[:max_len]

    def _methods(self):
        out = []
        for m in METHOD_RE.finditer(self.skel):
            name = m.group(2)
            if name in ("if", "for", "foreach", "while", "switch", "using", "lock", "catch", "return", "new"):
                continue
            ob = m.end() - 1
            cb = match_close(self.skel, ob)
            header = self.skel[m.start():ob]
            out.append({"name": name, "start": m.start(), "body_start": ob, "body_end": cb,
                        "async": bool(re.search(r"\basync\b", header)), "params": m.group(3),
                        "ret": m.group(1), "public": bool(re.search(r"\bpublic\b", header))})
        return out

    def _loops(self):
        out = []
        for m in LOOP_RE.finditer(self.skel):
            kind = m.group(1) or ("ParallelForEach" if "Parallel" in m.group(0) else "ForEach")
            po = m.end() - 1
            pc = match_close(self.skel, po)
            if kind in ("ForEach", "ParallelForEach"):
                out.append({"kind": kind, "start": m.start(), "body_start": po, "body_end": pc, "header": self.clean[m.start():po + 1]})
                continue
            k = pc + 1
            while k < len(self.skel) and self.skel[k].isspace():
                k += 1
            if k < len(self.skel) and self.skel[k] == "{":
                be = match_close(self.skel, k)
            else:
                be = self.skel.find(";", k)
                be = len(self.skel) if be == -1 else be
            # 'while (...);' closing a do-while: skip
            if kind == "while" and k < len(self.skel) and self.skel[k] == ";":
                continue
            out.append({"kind": kind, "start": m.start(), "body_start": k, "body_end": be, "header": self.clean[m.start():pc + 1]})
        return out

    def method_at(self, off):
        best = None
        for m in self.methods:
            if m["body_start"] <= off <= m["body_end"]:
                if best is None or m["body_start"] > best["body_start"]:
                    best = m
        return best

    def in_loop(self, off):
        return any(l["body_start"] <= off <= l["body_end"] for l in self.loops)


# ----------------------------------------------------------------------------- scanner

class Scanner:
    def __init__(self, root, ef_version=None, target=None, include_tests=False, max_per_rule=50):
        self.root = Path(root).resolve()
        self.detect = detect_ef.detect(self.root)
        flav, major = detect_ef.primary(self.detect)
        self.flavour, self.major = flav, major
        self.forced = bool(ef_version)
        if ef_version:
            self.flavour, self.major = ("EF6", 6) if ef_version == 6 else ("EF Core", ef_version)
        self.target = target
        self.include_tests = include_tests
        self.max_per_rule = max_per_rule
        self.findings = []
        self.files = []
        self.test_files = []
        self.config_files = []
        self.repo_text = ""

    # -- helpers
    def is_ef6(self):
        return self.flavour == "EF6"

    def proj_for(self, rel):
        best = None
        for p in self.detect["projects"]:
            d = p["dir"]
            if d == "." or rel == d or rel.startswith(d.rstrip("/\\") + os.sep) or rel.startswith(d.rstrip("/\\") + "/"):
                if p["flavour"] and (best is None or len(d) > len(best["dir"])):
                    best = p
        return best

    def add(self, rid, f, off, message, fix="", confidence="medium", file_override=None, line_override=None, snippet=None):
        cat, sev, title, ref, min_core, core_only = RULES[rid]
        note = ""
        saved = (self.flavour, self.major)
        p = self.proj_for(f.rel) if f else None
        if p and not self.forced:
            self.flavour, self.major = p["flavour"], p["ef_major"]
        try:
            return self._add(rid, f, off, message, fix, confidence, file_override, line_override, snippet,
                             cat, sev, title, ref, min_core, core_only, note)
        finally:
            self.flavour, self.major = saved

    def _add(self, rid, f, off, message, fix, confidence, file_override, line_override, snippet,
             cat, sev, title, ref, min_core, core_only, note):
        if self.is_ef6() and core_only:
            if rid in ("EF011", "EF012"):
                note = "EF6 has no ExecuteUpdate/Delete: use parameterised ExecuteSqlCommand or upgrade to EF Core 7+."
                sev = "low"
            else:
                return
        elif min_core and self.flavour == "EF Core" and self.major and self.major < min_core:
            note = f"Needs EF Core {min_core}+ (current {self.major}): suggest after upgrade."
            sev = "info"
        elif min_core and self.is_ef6():
            note = f"Needs EF Core {min_core}+ (project is EF6)."
            sev = "info"
        self.findings.append({
            "id": rid, "severity": sev, "category": cat, "title": title,
            "file": file_override or (f.rel if f else None),
            "line": line_override if line_override is not None else (f.line(off) if f else None),
            "snippet": snippet if snippet is not None else (f.snippet(off) if f else ""),
            "message": message + ((" " + note) if note else ""), "fix": fix,
            "min_ef_core": min_core, "reference": f"references/{ref}", "confidence": confidence,
        })

    def walk(self):
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                yield Path(dirpath) / fn

    def load(self):
        test_dirs = [self.root / p["dir"] for p in self.detect["projects"] if p["is_test"]]
        for p in self.walk():
            rel = str(p.relative_to(self.root))
            low = p.name.lower()
            if p.suffix == ".cs":
                text = detect_ef.read(p)
                if not text:
                    continue
                if low.endswith((".designer.cs", ".g.cs", ".generated.cs")) and "Migration" not in text:
                    continue
                is_test = any(str(p).startswith(str(td) + os.sep) for td in test_dirs) or bool(
                    re.search(r"(^|[\\/])[^\\/]*tests?[\\/]", rel, re.I))
                sf = SrcFile(p, rel, text)
                (self.test_files if is_test else self.files).append(sf)
            elif low.startswith("appsettings") and low.endswith(".json") or low in ("web.config", "app.config") \
                    or p.suffix == ".csproj":
                self.config_files.append((rel, detect_ef.read(p)))
        if self.include_tests:
            self.files += self.test_files
        self.repo_text = "\n".join(f.clean for f in self.files)

    def discover_ctx(self):
        types = set()
        alltext = self.repo_text + "\n" + "\n".join(f.clean for f in self.test_files)
        for m in re.finditer(r"class\s+(\w+)\s*(?:<[^>]*>)?\s*:\s*([\w.]*?(DbContext|IdentityDbContext|ObjectContext)\b)", alltext):
            types.add(m.group(1))
        changed = True
        while changed:
            changed = False
            for m in re.finditer(r"class\s+(\w+)\s*:\s*([\w.]+)", alltext):
                if m.group(2).split(".")[-1] in types and m.group(1) not in types:
                    types.add(m.group(1)); changed = True
        types -= NOT_CTX_TYPES
        self.ctx_types = sorted(types) or []
        type_alt = "|".join(map(re.escape, self.ctx_types + ["DbContext"]))
        names = set(DEFAULT_CTX_NAMES)
        for m in re.finditer(rf"\b(?:{type_alt})\s+(\w+)\s*[;=,)]", alltext):
            names.add(m.group(1))
        for m in re.finditer(rf"var\s+(\w+)\s*=\s*(?:new\s+(?:{type_alt})\s*\(|\w+\s*\.\s*CreateDbContext(?:Async)?\s*\()", alltext):
            names.add(m.group(1))
        names -= {"this", "base"}
        self.ctx_names = sorted(names, key=len, reverse=True)
        self.ctx_type_re = type_alt
        alt = "|".join(map(re.escape, self.ctx_names))
        self.ctx_access = re.compile(rf"(?<![\w.])(?:this\s*\.\s*)?(?:{alt})\s*\.\s*(?:Set\s*<[\w.]+>\s*\(\s*\)|[A-Z]\w*)")
        self.dbset_types = set(re.findall(r"\b(?:I?DbSet|IQueryable)\s*<\s*(\w+)\s*>", self.repo_text))

    def ctx_statements(self, f, lo=0, hi=None):
        """Yield (start, end, clean_stmt) for statements that touch the context, deduped."""
        hi = len(f.skel) if hi is None else hi
        seen = set()
        for m in self.ctx_access.finditer(f.skel, lo, hi):
            s, e = statement_span(f.skel, m.start(), lo, hi)
            if (s, e) in seen:
                continue
            seen.add((s, e))
            yield s, e, f.clean[s:e], f.skel[s:e]

    def global_has(self, pattern, flags=0):
        return re.search(pattern, self.repo_text, flags) is not None

    # -- rules over code
    def rules_code(self, f):
        sk, cl = f.skel, f.clean
        mat = re.compile(rf"\.\s*(?:{MATERIALISERS})\s*\(")
        # EF001 / EF004 / EF011 / EF012 loops
        for lp in f.loops:
            body_s, body_e = lp["body_start"], lp["body_end"]
            if lp["kind"] in ("ForEach", "ParallelForEach"):
                pass
            first_q, first_save, first_repo, first_remove = None, None, None, None
            for s, e, stmt, sstmt in self.ctx_statements(f, body_s, body_e + 1):
                if re.search(r"\bSaveChanges(?:Async)?\s*\(", sstmt):
                    first_save = first_save or s
                    continue
                if re.search(r"\.\s*Remove\s*\(", sstmt) and not mat.search(sstmt):
                    first_remove = first_remove or s
                    continue
                if mat.search(sstmt) or re.search(r"\bawait\b", sstmt) and re.search(r"Async\s*\(", sstmt):
                    if not re.search(r"\.\s*(?:Add|AddAsync|AddRange|Update|Attach|Entry|Remove)\s*\(", sstmt) or mat.search(sstmt):
                        first_q = first_q or s
            rm = re.search(r"\bawait\s+_?\w*[Rr]epo(?:sitory)?\w*\s*\.\s*(?:Get|Find|Load|Fetch|Query)\w*\s*\(", sk[body_s:body_e])
            if rm:
                first_repo = body_s + rm.start()
            if first_q is not None:
                self.add("EF001", f, first_q, f"Database query inside `{lp['kind']}` loop runs once per item.",
                         "Load everything needed in one query before the loop (Where + Contains, Include, or projection), then look up in memory.")
            elif first_repo is not None:
                self.add("EF001", f, first_repo, "Repository call inside loop: likely one query per item.",
                         "Add a batch method (GetByIds) and call it once before the loop.", confidence="low")
            if first_save is not None:
                self.add("EF004", f, first_save, f"SaveChanges inside `{lp['kind']}` loop: one round trip and transaction per item.",
                         "Call SaveChanges once after the loop (chunk very large batches).")
            if first_remove is not None:
                self.add("EF011", f, first_remove, "Entities deleted one by one in a loop after loading them.",
                         "Use query.Where(...).ExecuteDelete(Async)(); check for soft-delete/audit SaveChanges overrides first.")
            # EF012: foreach over query result assigning properties
            hm = re.match(r"foreach\s*\(\s*(?:var|[\w<>.]+)\s+(\w+)\s+in\s+(.+)\)\s*$", lp["header"].strip(), re.S)
            if hm and first_q is None:
                var, src = hm.group(1), hm.group(2)
                body = sk[body_s:body_e]
                assigns = re.findall(rf"\b{re.escape(var)}\s*\.\s*\w+\s*(?:=(?!=)|\+=|-=)", body)
                from_query = bool(self.ctx_access.search(src))
                if not from_query and re.fullmatch(r"\w+", src.strip()):
                    meth = f.method_at(lp["start"])
                    if meth:
                        mtxt = sk[meth["body_start"]:lp["start"]]
                        from_query = bool(re.search(rf"\b{re.escape(src.strip())}\s*=\s*(?:await\s+)?[^;]*?" + self.ctx_access.pattern, mtxt))
                if assigns and from_query and len(re.findall(r";", body)) <= len(assigns) + 1:
                    meth = f.method_at(lp["start"])
                    after = sk[body_e:meth["body_end"]] if meth else ""
                    if re.search(r"SaveChanges(?:Async)?\s*\(", after):
                        self.add("EF012", f, lp["start"], "Loads entities then sets properties in a loop and saves: set-based update candidate.",
                                 "Use ExecuteUpdate(Async)(s => s.SetProperty(...)) if no audit/concurrency logic depends on tracking.", confidence="low")

        # RemoveRange of loaded list
        for m in re.finditer(r"\.\s*RemoveRange\s*\(", sk):
            s, e = statement_span(sk, m.start())
            if re.search(r"(?:ToList|ToListAsync|ToArray)\s*\(|\.\s*Where\s*\(", sk[s:e]):
                self.add("EF011", f, m.start(), "RemoveRange over a query result loads rows just to delete them.",
                         "Use query.ExecuteDelete(Async)().")

        for meth in f.methods:
            bs, be = meth["body_start"], meth["body_end"]
            body = sk[bs:be]
            stmts = list(self.ctx_statements(f, bs, be))
            writes = re.search(r"\b(?:SaveChanges(?:Async)?|Update|UpdateRange|Remove|RemoveRange|Add|AddAsync|AddRange|Attach|Entry)\s*\(", body)
            # EF007 sync in async
            if meth["async"]:
                for s, e, stmt, sstmt in stmts:
                    if re.search(rf"\.\s*(?:{SYNC_MAT})\s*\(", sstmt) and "Async(" not in sstmt.replace(" ", "") \
                            and not re.search(r"\bawait\b", sstmt):
                        self.add("EF007", f, s, f"Synchronous EF call in async method `{meth['name']}` blocks a thread.",
                                 "Use the Async version (ToListAsync, FirstOrDefaultAsync, SaveChangesAsync) and pass a CancellationToken.")
                        break
            # EF010 read-only without AsNoTracking
            if re.match(r"(?:Get|List|Find|Search|Fetch|Load|Query|Read|Export|Report|Browse|Lookup)", meth["name"]) and not writes \
                    and not self.global_notracking:
                for s, e, stmt, sstmt in stmts:
                    if mat.search(sstmt) and "AsNoTracking" not in sstmt and not re.search(r"\.\s*Select\s*\(|\bDatabase\s*\.", sstmt) \
                            and not re.search(r"\.\s*(?:Count|CountAsync|Any|AnyAsync|Sum|SumAsync|Max|MaxAsync|Min|MinAsync|Average|AverageAsync|LongCount)\s*\(", sstmt) \
                            and not re.search(r"\bFind(?:Async)?\s*\(", sstmt):
                        self.add("EF010", f, s, f"`{meth['name']}` only reads, but the query tracks entities.",
                                 "Add .AsNoTracking() or project to a DTO with Select. Skip if the entities are modified later by the caller.",
                                 confidence="low")
                        break
            # EF301 multiple SaveChanges without transaction
            saves = [m for m in re.finditer(r"\bSaveChanges(?:Async)?\s*\(", body) if not f.in_loop(bs + m.start())]
            if len(saves) >= 2 and not re.search(r"BeginTransaction|TransactionScope|CreateExecutionStrategy|UseTransaction", body):
                self.add("EF301", f, bs + saves[1].start(), f"`{meth['name']}` calls SaveChanges {len(saves)} times with no transaction: partial commits possible.",
                         "Use a single SaveChanges, or wrap in BeginTransaction (inside CreateExecutionStrategy().Execute if retries are on).")
            # EF018 parallel on one context
            if re.search(r"Task\s*\.\s*WhenAll\s*\(|Parallel\s*\.\s*ForEach|\.AsParallel\s*\(", body) and stmts:
                wm = re.search(r"Task\s*\.\s*WhenAll\s*\(", body)
                direct = False
                if wm:
                    a = bs + wm.end() - 1
                    args = sk[a:match_close(sk, a)]
                    direct = bool(self.ctx_access.search(args))
                    tasks_from_ctx = re.search(r"\.\s*Select\s*\(\s*(?:async\s*)?\(?\w*\)?\s*=>[^;]*?" + self.ctx_access.pattern, body)
                    if direct or tasks_from_ctx:
                        self.add("EF018", f, a, "Task.WhenAll runs several queries on the same DbContext concurrently.",
                                 "Await sequentially, or create one context per branch with IDbContextFactory.",
                                 confidence="medium" if direct else "low")
                elif re.search(r"Parallel\s*\.\s*ForEach", body):
                    pm = re.search(r"Parallel\s*\.\s*ForEach", body)
                    self.add("EF018", f, bs + pm.start(), "Parallel.ForEach with DbContext usage in the same method: check the context is not shared across threads.",
                             "Create a context per iteration via IDbContextFactory, or run sequentially.", confidence="low")

        for s, e, stmt, sstmt in self.ctx_statements(f):
            flat = re.sub(r"\s+", "", sstmt)
            # EF002 materialise then filter
            m2 = re.search(r"\.(ToList|ToArray|AsEnumerable|ToListAsync\([^)]*\)\))\(\)\.(Where|OrderBy|OrderByDescending|Select|Count|Any|First|FirstOrDefault|Single|SingleOrDefault|Skip|Take|Sum|GroupBy|Distinct|Max|Min)\(", flat) \
                or re.search(r"ToListAsync\([^)]*\)\)\.(Where|OrderBy|Skip|Take|First|FirstOrDefault|Count|Any|GroupBy)\(", flat)
            if m2:
                after = m2.group(2) if m2.lastindex and m2.lastindex >= 2 else m2.group(1)
                self.add("EF002", f, s, f"Query is materialised, then `{after}` runs in memory.",
                         "Move the filter/paging/aggregate before ToList so it runs in SQL. AsEnumerable is fine only at the very end for untranslatable C#.")
            # EF003
            if re.search(r"\.Count(?:Async)?\([^;]*?\)(?:>0|!=0|>=1)|0<[^;]*?\.Count(?:Async)?\(", flat):
                self.add("EF003", f, s, "Count() compared with 0 scans all matches.", "Use Any()/AnyAsync() (EXISTS).")
            # EF009 multiple includes
            inc = len(re.findall(r"\.(?:Include|ThenInclude)\(", flat))
            if inc >= 2 and "AsSplitQuery" not in flat and not self.global_split and re.search(rf"\.(?:{MATERIALISERS})\(", flat):
                self.add("EF009", f, s, f"{inc} Include/ThenInclude in one query: if 2+ are collections, rows multiply (cartesian explosion).",
                         "Add .AsSplitQuery() (or project with Select). Needs a stable OrderBy when paging.", confidence="low")
            # EF013 unbounded load
            if re.search(r"\.(?:ToList|ToListAsync|ToArray|ToArrayAsync)\(", flat) and not re.search(
                    r"\.(?:Where|Take|Skip|First|FirstOrDefault|Single|Find|Any|Count|Max|Min|Sum|GroupBy|FromSql\w*|SqlQuery\w*|TakeWhile|Distinct)\b", flat) \
                    and not re.search(r"\bwhere\b", stmt) and re.search(r"(?:" + "|".join(map(re.escape, self.ctx_names)) + r")\.(?!Database\b)[A-Z]\w*\.", flat):
                self.add("EF013", f, s, "Loads every row of the table with no filter or paging.",
                         "Filter and page in SQL (Where + OrderBy + Skip/Take or keyset). For exports, stream with AsAsyncEnumerable + AsNoTracking. OK for small lookup tables.",
                         confidence="low")
            # EF014 contains on list
            if re.search(r"\b[a-z_]\w*\.Contains\(\w+\.\w+\)", flat) and re.search(r"=>", flat):
                self.add("EF014", f, s, "In-memory list Contains() becomes a SQL IN / OPENJSON / parameter list; slow and plan-cache heavy if the list is large.",
                         "Cap or chunk the list; for very large sets use a temp table/TVP. Behaviour differs by EF version (see reference).", confidence="low")
            # EF015 non-sargable
            m15 = re.search(r"=>[^;]*?\b\w+\.\w+(?:\.\w+)*\.(ToLower|ToUpper|ToLowerInvariant|ToUpperInvariant|Trim|TrimStart|TrimEnd)\(\)", flat) \
                or re.search(r"=>[^;]*?\b\w+\.\w+\.(Date|Year|Month|Day)(?:==|!=|>|<)", flat)
            if m15 and re.search(r"\.(?:Where|First\w*|Single\w*|Any\w*|Count\w*|OrderBy\w*)\(", flat):
                self.add("EF015", f, s, f"`{m15.group(1)}` on a column inside the predicate stops index seeks.",
                         "Rely on case-insensitive collation, normalise data on write, or use a range (x.Date >= d && x.Date < d.AddDays(1)).")
            # EF016 include + select
            if re.search(r"\.Include\([^;]*\.Select\(", flat) and not re.search(r"\.Select\([^;]*\.Include\(", flat):
                self.add("EF016", f, s, "Include followed by Select projection: the Include is ignored.",
                         "Remove the Include or select the needed navigation fields in the projection.", confidence="low")
            # EF504
            if ".ToAsyncEnumerable()" in flat:
                self.add("EF504", f, s, "ToAsyncEnumerable on an EF query uses the sync enumerator.", "Use AsAsyncEnumerable().")
            # EF701 / EF706 / EF702
            if re.search(r"GroupJoin\(", flat) and "DefaultIfEmpty" in flat:
                self.add("EF701", f, s, "Left join written with GroupJoin + SelectMany + DefaultIfEmpty.", "Use .LeftJoin(...) (EF Core 10+).")
            if re.search(r"\.(?:Union|Concat)\(", flat) and "DefaultIfEmpty" in flat:
                self.add("EF706", f, s, "Looks like a full outer join emulated with left/right joins + Union.", "Use .FullJoin(...) (EF Core 11+).", confidence="low")
            if re.search(r"\.OrderBy(?:Descending)?\([^()]*\)\.(?:First|FirstOrDefault)(?:Async)?\((?:\)|cancellationToken\)|ct\))", flat):
                self.add("EF702", f, s, "OrderBy(...).First() to get the min/max element.", "Use MaxBy/MinBy (MaxByAsync) on EF Core 11+.")

        # query syntax left join
        for m in re.finditer(r"\binto\s+\w+\s+from\s+\w+\s+in\s+\w+\s*\.\s*DefaultIfEmpty\s*\(", sk):
            self.add("EF701", f, m.start(), "Query-syntax left join (join ... into ... DefaultIfEmpty).", "Use .LeftJoin(...) (EF Core 10+).")

        # EF003 also for non-ctx variables that are IQueryable? skip (noise).

        # EF005 raw SQL injection
        for m in re.finditer(r"\b(FromSqlRaw|ExecuteSqlRaw(?:Async)?|SqlQueryRaw|SqlQuery\s*<[^>]+>|SqlQuery|ExecuteSqlCommand(?:Async)?)\s*\(", sk):
            a = m.end() - 1
            args = cl[a + 1:match_close(sk, a)]
            first = args.split(",")[0].strip()
            bad = re.match(r"\$@?\"|@\$\"", first) or re.search(r"\"\s*\+|\+\s*\"|string\s*\.\s*(?:Format|Concat)", first)
            conf = "high"
            if not bad and re.fullmatch(r"[A-Za-z_]\w*", first):
                meth = f.method_at(m.start())
                scope = cl[meth["body_start"]:m.start()] if meth else cl[max(0, m.start() - 2000):m.start()]
                if re.search(rf"\b{re.escape(first)}\s*(?:=|\+=)\s*[^;]*(?:\$\"|\"\s*\+|\+\s*\w|string\s*\.\s*(?:Format|Concat)|StringBuilder)", scope) \
                        or re.search(rf"\b{re.escape(first)}\s*\.\s*Append", scope):
                    bad, conf = True, "medium"
            if bad:
                self.add("EF005", f, m.start(), f"`{m.group(1)}` gets a SQL string built from values: SQL injection risk.",
                         "Use FromSql/ExecuteSql with an interpolated string (parameterised), or pass parameters ({0} / SqlParameter). Whitelist dynamic identifiers.",
                         confidence=conf)

        # EF006 blocking on async
        for m in re.finditer(r"(\w+Async)\s*\([^;]*?\)\s*\.\s*(Result\b|Wait\s*\(\s*\)|GetAwaiter\s*\(\s*\)\s*\.\s*GetResult\s*\(\s*\))", sk):
            s, e = statement_span(sk, m.start())
            if self.ctx_access.search(sk[s:e]) or re.match(rf"(?:{MATERIALISERS}|SaveChangesAsync|ExecuteSqlRawAsync|ExecuteUpdateAsync|ExecuteDeleteAsync)$", m.group(1)):
                self.add("EF006", f, m.start(), f"`{m.group(1)}(...).{m.group(2).split('(')[0]}` blocks the thread; deadlock/thread starvation risk.",
                         "Make the call chain async and await it (or use the sync EF API consistently in legacy sync code).")

        # EF008 lifetime
        tr = self.ctx_type_re
        for m in re.finditer(rf"AddSingleton\s*<\s*(?:{tr})\s*>|AddSingleton\s*\(\s*typeof\s*\(\s*(?:{tr})\s*\)|AddDbContext\w*\s*<[^>]*>\s*\([^;]*ServiceLifetime\s*\.\s*Singleton", sk):
            self.add("EF008", f, m.start(), "DbContext registered as singleton: shared across requests and threads.",
                     "Use scoped AddDbContext; in singletons use IDbContextFactory.")
        for m in re.finditer(rf"\bstatic\s+(?:readonly\s+)?(?:{tr})\s+\w+", sk):
            self.add("EF008", f, m.start(), "Static DbContext field: one context for the whole app.",
                     "Create a context per request/unit of work (DI scoped, or using new ... per operation).")
        for m in re.finditer(rf"(?:Session|Application|HttpRuntime\s*\.\s*Cache|MemoryCache\w*)\s*\[[^\]]+\]\s*=\s*(?:new\s+(?:{tr})|{'|'.join(map(re.escape, self.ctx_names))})\b", sk):
            self.add("EF008", f, m.start(), "DbContext stored in Session/Application/cache.", "Never cache a DbContext; create one per request.")

        # EF017 lazy loading
        for m in re.finditer(r"UseLazyLoadingProxies\s*\(|LazyLoadingEnabled\s*=\s*true", sk):
            self.add("EF017", f, m.start(), "Lazy loading is enabled: navigation access in loops/views/serialisers triggers hidden queries.",
                     "Prefer explicit Include/projection; disable lazy loading for read/API paths.")

        # EF103 cascade
        for m in re.finditer(r"OnDelete\s*\(\s*DeleteBehavior\s*\.\s*Cascade\s*\)|WillCascadeOnDelete\s*\(\s*(?:true\s*)?\)", sk):
            self.add("EF103", f, m.start(), "Cascade delete: deleting the parent deletes all children.",
                     "Confirm intent; for business data prefer Restrict/NoAction + soft delete.", confidence="low")
        # EF105 owned
        for m in re.finditer(r"\.\s*Owns(?:One|Many)\s*\(", sk):
            self.add("EF105", f, m.start(), "Owned type mapping; complex types are the newer value-object mapping.",
                     "Consider ComplexProperty (EF8+, JSON in EF10+, keys/indexes and TPT/TPC in EF11).")
        # EF705 combined filter
        for m in re.finditer(r"HasQueryFilter\s*\(", sk):
            a = m.end() - 1
            args = sk[a:match_close(sk, a)]
            if "&&" in args and not re.match(r"\(\s*\"", cl[a:a + 5]):
                self.add("EF705", f, m.start(), "Several conditions combined in one query filter; IgnoreQueryFilters removes all of them.",
                         "Use named filters (EF Core 10+) so you can ignore only one, e.g. soft delete but not tenant.")

        # EF205 / EF206
        if "Migrations" not in f.rel.replace("\\", "/").split("/"):
            for m in re.finditer(r"\.\s*Migrate(?:Async)?\s*\(", sk):
                if self.ctx_access.search(sk[max(0, m.start() - 80):m.end()]) or "Database" in sk[max(0, m.start() - 40):m.start()]:
                    self.add("EF205", f, m.start(), "Migrations applied at application startup.",
                             "Apply migrations from the pipeline (idempotent script or bundle). On EF Core 9+ this throws if the model has pending changes.")
                    if self.target and self.flavour == "EF Core" and (self.major or 0) < 9 <= self.target:
                        self.add("EF807", f, m.start(), "After upgrading to EF Core 9+, Migrate() throws PendingModelChangesWarning when the model and migrations differ.",
                                 "Run `dotnet ef migrations has-pending-model-changes` in CI before upgrading.")
            for m in re.finditer(r"\bEnsureCreated(?:Async)?\s*\(", sk):
                self.add("EF206", f, m.start(), "EnsureCreated bypasses migrations; DB cannot be migrated later.", "Use migrations outside tests.")

        # EF401 / EF404
        for m in re.finditer(r"\b(EnableSensitiveDataLogging|EnableDetailedErrors)\s*\(", sk):
            ctxwin = cl[max(0, m.start() - 400):m.end() + 80]
            if not re.search(r"IsDevelopment|#if\s+DEBUG|IsEnvironment|Debugger\.IsAttached", ctxwin):
                rid = "EF401" if m.group(1) == "EnableSensitiveDataLogging" else "EF404"
                self.add(rid, f, m.start(), f"{m.group(1)} is not guarded by a development check.",
                         "Wrap in if (env.IsDevelopment()) ... or drive it from configuration that is off in production.")
        # EF403
        for m in re.finditer(r"\.\s*IgnoreQueryFilters\s*\(", sk):
            self.add("EF403", f, m.start(), "Global query filters are bypassed here.",
                     "Confirm admin-only use and that tenant filtering is still applied; with EF Core 10 ignore only the named filter you need.", confidence="low")

        # EF402 secrets in code
        for m in re.finditer(r"\"[^\"\n]*(?:Password|Pwd)\s*=\s*([^;\"\n]+)", cl, re.I):
            if not SECRET_PLACEHOLDER.match(m.group(1)) and "{" not in m.group(1):
                self.add("EF402", f, m.start(), "Connection string with a password hard-coded in source.",
                         "Move to user-secrets / Key Vault / environment variables or use Managed Identity; rotate the password.",
                         snippet=re.sub(r"((?:Password|Pwd)\s*=\s*)[^;\"]+", r"\1****", f.snippet(m.start()), flags=re.I))

        # EF502 hosted service with context ctor param
        for m in re.finditer(r"class\s+(\w+)[^{]*:\s*[^{]*\b(BackgroundService|IHostedService)\b", sk):
            cname = m.group(1)
            ob = sk.find("{", m.end())
            if ob == -1:
                continue
            cbody = sk[ob:match_close(sk, ob)]
            prim = re.search(rf"class\s+{cname}\s*\(([^)]*)\)", sk[m.start():ob])
            ctor = re.search(rf"\b{cname}\s*\(([^)]*)\)", cbody)
            params = (prim.group(1) if prim else "") + (ctor.group(1) if ctor else "")
            if re.search(rf"\b(?:{tr})\s+\w+", params):
                self.add("EF502", f, m.start(), f"`{cname}` is a long-lived hosted service but takes a DbContext in its constructor.",
                         "Inject IDbContextFactory<T> or IServiceScopeFactory and create a context per unit of work.")

        # EF505 new context without using
        for m in re.finditer(rf"\bnew\s+({tr})\s*\(", sk):
            if m.group(1) == "DbContext":
                continue
            line_start = sk.rfind("\n", 0, m.start()) + 1
            prefix = sk[line_start:m.start()]
            if "using" in prefix or re.search(r"\breturn\b|=>\s*$", prefix) or re.search(r"Create\w*Context", sk[max(0, m.start() - 200):m.start()]):
                continue
            meth = f.method_at(m.start())
            body = sk[meth["body_start"]:meth["body_end"]] if meth else ""
            vm = re.match(r"\s*(?:var|\w+)\s+(\w+)\s*=\s*$", prefix)
            if vm and re.search(rf"\b{vm.group(1)}\s*\.\s*Dispose\s*\(", body):
                continue
            self.add("EF505", f, m.start(), f"`new {m.group(1)}(...)` without using/Dispose: leaked connections and change trackers.",
                     "Wrap in using / await using, or get it from DI / IDbContextFactory.", confidence="low")

        # EF601 / EF602
        for m in re.finditer(r"\b(?:interface\s+I\w*Repository\s*<\s*T\w*\s*>|class\s+\w*Repository\s*<\s*T\w*\s*>)", sk):
            self.add("EF601", f, m.start(), "Generic repository wrapping DbSet.",
                     "Check GetAll/Find return IQueryable-friendly results; prefer specific query methods returning DTOs on hot paths.")
        for meth in f.methods:
            if meth["public"] and re.match(r"IQueryable\s*<", meth["ret"]) and not re.search(rf"class\s+\w+\s*:\s*[\w.]*(?:{tr})", sk):
                self.add("EF602", f, meth["start"], f"`{meth['name']}` returns IQueryable: query runs later, outside the data layer.",
                         "Return materialised DTOs, or keep IQueryable internal to the data layer.", confidence="low")

        # EF803 / EF806 (only with target 11)
        if self.target and self.target >= 11:
            for m in re.finditer(r"\bUseSqlServer\s*\(", sk):
                a = m.end() - 1
                if "UseCompatibilityLevel" not in sk[a:match_close(sk, a)] and "UseCompatibilityLevel" not in self.repo_text:
                    self.add("EF803", f, m.start(), "EF Core 11 defaults SQL Server compatibility level to 160 (2022).",
                             "If prod runs an older SQL Server/compat level, add o => o.UseCompatibilityLevel(150) (or your level).")
            if re.search(r"\bUseCosmos\s*\(", sk) and re.search(r"__jObject|Newtonsoft", cl):
                mm = re.search(r"__jObject|Newtonsoft", cl)
                self.add("EF806", f, mm.start(), "Cosmos code relies on __jObject/Newtonsoft, both gone in EF Core 11.",
                         "Map needed properties explicitly; review System.Text.Json differences and id escaping changes.")

    def rules_entities(self):
        """EF101 / EF102 on DbSet entity classes."""
        if not self.dbset_types:
            return
        global_prec = self.global_has(r"Properties\s*<\s*decimal\??\s*>\s*\(\s*\)\s*\.\s*HavePrecision|HaveColumnType\(\"decimal")
        global_len = self.global_has(r"Properties\s*<\s*string\s*>\s*\(\s*\)\s*\.\s*HaveMaxLength")
        for f in self.files:
            for m in re.finditer(r"\b(?:public\s+)?(?:partial\s+)?class\s+(\w+)", f.skel):
                cname = m.group(1)
                if cname not in self.dbset_types:
                    continue
                ob = f.skel.find("{", m.end())
                if ob == -1:
                    continue
                cb = match_close(f.skel, ob)
                body = f.skel[ob:cb]
                strings_wo_len = []
                for pm in re.finditer(r"((?:\[[^\]]*\]\s*)*)public\s+(decimal|string)\??\s+(\w+)\s*\{", body):
                    attrs, typ, prop = pm.group(1), pm.group(2), pm.group(3)
                    off = ob + pm.start(2)
                    cfg = rf"\.\s*Property\s*\(\s*\w+\s*=>\s*\w+\s*\.\s*{prop}\s*\)[^;]*"
                    if typ == "decimal" and not global_prec and "Precision" not in attrs and "Column(TypeName" not in attrs.replace(" ", ""):
                        if not re.search(cfg + r"(?:HasPrecision|HasColumnType)", self.repo_text):
                            self.add("EF101", f, off, f"`{cname}.{prop}` is decimal with no precision: defaults to decimal(18,2), values can be truncated.",
                                     "Add [Precision(18,4)] / .HasPrecision(p,s), or a ConfigureConventions default.")
                    if typ == "string" and not global_len and not re.search(r"MaxLength|StringLength|Column\(TypeName", attrs):
                        if not re.search(cfg + r"(?:HasMaxLength|HasColumnType|IsFixedLength)", self.repo_text):
                            strings_wo_len.append(prop)
                if strings_wo_len and not global_len:
                    self.add("EF102", f, m.start(), f"`{cname}` has {len(strings_wo_len)} string properties without max length: {', '.join(strings_wo_len[:8])}" +
                             ("..." if len(strings_wo_len) > 8 else "") + ". They become nvarchar(max).",
                             "Add [MaxLength]/HasMaxLength or a ConfigureConventions default; IsUnicode(false) for ASCII codes.", confidence="low")

    def rules_migrations(self):
        for f in self.files:
            if not re.search(r"class\s+\w+\s*:\s*(?:[\w.]*\.)?(?:Migration|DbMigration)\b", f.skel):
                continue
            um = re.search(r"\b(?:protected\s+)?(?:override\s+)?void\s+Up\s*\([^)]*\)\s*\{", f.skel)
            if not um:
                continue
            ob = um.end() - 1
            cb = match_close(f.skel, ob)
            seg = f.skel[ob:cb]
            for m in re.finditer(r"\b(?:migrationBuilder\s*\.\s*)?(DropColumn|DropTable|DeleteData|DropForeignKey|DropPrimaryKey|RenameColumn|RenameTable|AlterColumn|Sql)\s*\(", seg):
                op, off = m.group(1), ob + m.start()
                if op in ("DropColumn", "DropTable", "DeleteData"):
                    self.add("EF201", f, off, f"`{op}` in migration Up(): data is lost.",
                             "Make sure data is migrated/backed up first; if this is a rename EF generated as drop+add, use RenameColumn.")
                elif op in ("RenameColumn", "RenameTable"):
                    self.add("EF202", f, off, f"`{op}`: older app instances, views, procs and raw SQL using the old name will break.",
                             "Use expand/contract for zero-downtime deploys; search raw SQL for the old name.", confidence="low")
                elif op == "AlterColumn":
                    self.add("EF203", f, off, "AlterColumn: can fail on existing data (nullability/length) or lock a big table.",
                             "Check existing data fits; add defaultValue for not-null; run off-peak on large tables.", confidence="low")
                elif op == "Sql":
                    self.add("EF204", f, off, "Raw SQL in migration: check idempotency, provider syntax and size of data changes.",
                             "Batch large updates; keep scripts idempotent.", confidence="low")

    def rules_config(self):
        for rel, text in self.config_files:
            low = rel.lower()
            if low.endswith(".csproj"):
                if "EFOptimizeContext" in text and self.target and self.target >= 11:
                    ln = text[:text.find("EFOptimizeContext")].count("\n") + 1
                    self.add("EF805", None, 0, "EFOptimizeContext property is removed in EF Core 11.",
                             "Delete it and use the current compiled model approach.", file_override=rel, line_override=ln, snippet="<EFOptimizeContext>")
                continue
            for m in re.finditer(r"(?:Password|Pwd)\s*=\s*([^;\"<\n]+)", text, re.I):
                val = m.group(1).strip()
                if not val or SECRET_PLACEHOLDER.match(val) or val.startswith("{") or "$(" in val:
                    continue
                ln = text[:m.start()].count("\n") + 1
                sev_note = "" if "development" in low else " (non-development config)"
                self.add("EF402", None, 0, f"Connection string with a password in committed config{sev_note}.",
                         "Use user-secrets / Key Vault / env vars / Managed Identity; rotate the password.",
                         file_override=rel, line_override=ln, snippet=re.sub(r"((?:Password|Pwd)\s*=\s*)[^;\"<]+", r"\1****", text.splitlines()[ln - 1].strip(), flags=re.I)[:160])
            if self.target and self.target >= 11:
                for m in re.finditer(r"Authentication\s*=\s*\"?\s*Active\s*Directory", text, re.I):
                    ln = text[:m.start()].count("\n") + 1
                    self.add("EF804", None, 0, "Entra ID authentication in connection string: EF Core 11 uses SqlClient 7, which moved Azure auth to a separate package.",
                             "Add the Azure authentication package named in the EF Core 11 breaking-changes doc.", file_override=rel, line_override=ln, snippet="Authentication=Active Directory ...")

    def rules_tests(self):
        for f in self.test_files:
            for m in re.finditer(r"\bUseInMemoryDatabase\s*\(", f.skel):
                self.add("EF603", f, m.start(), "Tests use the InMemory provider: no SQL translation, constraints or transactions.",
                         "Use SQLite in-memory for unit-ish tests and Testcontainers SQL Server for integration tests.")
                break

    def rules_project(self):
        rt = self.repo_text
        has_entities = bool(self.dbset_types)
        if has_entities and not re.search(r"IsRowVersion|\[Timestamp\]|IsConcurrencyToken|\[ConcurrencyCheck\]|\bRowVersion\b", rt):
            self.add("EF104", None, 0, "No concurrency token on any entity: concurrent edits silently overwrite each other.",
                     "Add a RowVersion to contested entities (orders, stock, balances) and handle DbUpdateConcurrencyException.",
                     file_override="(solution)", line_override=0, snippet="")
        if re.search(r"IsRowVersion|\[Timestamp\]|IsConcurrencyToken|\[ConcurrencyCheck\]", rt) and "DbUpdateConcurrencyException" not in rt:
            self.add("EF302", None, 0, "Concurrency tokens exist but DbUpdateConcurrencyException is never caught.",
                     "Catch it where entities are saved, reload/merge, return 409.", file_override="(solution)", line_override=0, snippet="")
        if re.search(r"\bUseSqlServer\s*\(|SqlServer", rt) and not re.search(r"EnableRetryOnFailure|UseAzureSql|SqlAzureExecutionStrategy|SetExecutionStrategy|ExecutionStrategy", rt):
            azure = any("database.windows.net" in t for _, t in self.config_files)
            self.add("EF303", None, 0, "No retry strategy for transient SQL errors" + (" and the app targets Azure SQL." if azure else "."),
                     "EF Core: EnableRetryOnFailure() or UseAzureSql(); EF6: SqlAzureExecutionStrategy.", file_override="(solution)", line_override=0, snippet="")
            if azure:
                self.findings[-1]["severity"] = "medium"
        if self.flavour == "EF Core" and has_entities and not re.search(r"\bTagWith(?:CallSite)?\s*\(", rt):
            self.add("EF604", None, 0, "No TagWith/TagWithCallSite: production SQL cannot be traced back to code.",
                     "Tag hot queries: .TagWith(\"Service.Method\") or .TagWithCallSite().", file_override="(solution)", line_override=0, snippet="")
        if has_entities and not re.search(r"\bLogTo\s*\(|AddInterceptors|DbCommandInterceptor|Database\s*\.\s*Log\s*=|DbInterception|EntityFrameworkCore\.Database\.Command|IDbCommandInterceptor|OpenTelemetry", rt + "".join(t for _, t in self.config_files)):
            self.add("EF605", None, 0, "No SQL logging, command interceptor or OpenTelemetry found.",
                     "Add a slow query interceptor (see slow-query-playbook.md) and OTel DB instrumentation.", file_override="(solution)", line_override=0, snippet="")
        if self.flavour == "EF Core" and re.search(r"\bAddDbContext\s*<", rt) and not re.search(r"AddDbContextPool|AddPooledDbContextFactory", rt):
            self.add("EF503", None, 0, "AddDbContext without pooling.", "For high-throughput APIs consider AddDbContextPool (if the context has no per-request state).",
                     file_override="(solution)", line_override=0, snippet="")
        has_ef6 = any(p["flavour"] == "EF6" for p in self.detect["projects"]) or self.is_ef6()
        if has_ef6 and re.search(r"public\s+virtual\s+(?:I?Collection|ICollection|List)\s*<", rt) and not re.search(r"LazyLoadingEnabled\s*=\s*false", rt):
            self.add("EF017", None, 0, "EF6 with virtual navigations and lazy loading never disabled: N+1 risk in views/serialisation.",
                     "Set Configuration.LazyLoadingEnabled = false on read/API contexts and use Include.", file_override="(solution)", line_override=0, snippet="")

    def rules_upgrade(self):
        today = date.today().isoformat()
        for p in self.detect["projects"]:
            if not p["flavour"] or p["is_test"]:
                continue
            if p["flavour"] == "EF Core" and p["support"] == "ended":
                self.add("EF801", None, 0, f"{p['project']} uses EF Core {p['ef_version']} ({p['support_note']}). Checked {today}.",
                         "Plan an upgrade to EF Core 10 (LTS) or 11.", file_override=p["path"], line_override=0, snippet=f"EF Core {p['ef_version']}")
            for w in p["warnings"]:
                if w.startswith("EF810"):
                    self.add("EF810", None, 0, w[6:], "Align all EF packages to one version (Central Package Management).",
                             file_override=p["path"], line_override=0, snippet="")
            if self.target and self.target >= 10 and any(re.match(r"net4\d", t) for t in p["target_frameworks"]):
                self.add("EF802", None, 0, f"{p['project']} targets .NET Framework ({', '.join(p['target_frameworks'])}); EF Core {self.target} needs .NET {self.target}.",
                         "Upgrade the runtime first, or stay on EF6 6.5 for this project.", file_override=p["path"], line_override=0, snippet="")
            if p["flavour"] == "EF6" and self.target:
                self.add("EF809", None, 0, f"{p['project']} is EF6 {p['ef_version']}: see EF6 to EF Core readiness table.",
                         "Fill in the readiness table in the report (EDMX, ObjectContext, lazy loading, client eval, stored procs).",
                         file_override=p["path"], line_override=0, snippet="")
        for w in self.detect["summary"]["solution_warnings"]:
            self.add("EF810", None, 0, w[6:], "Align all EF packages to one version.", file_override="(solution)", line_override=0, snippet="")
        if self.target:
            for e in self.detect["summary"]["edmx_files"]:
                self.add("EF809", None, 0, "EDMX designer model: EF Core has no EDMX; re-scaffold needed.",
                         "Scaffold with dotnet ef dbcontext scaffold or EF Core Power Tools.", file_override=e, line_override=0, snippet="")
            if re.search(r"\bObjectContext\b", self.repo_text):
                self.add("EF809", None, 0, "ObjectContext API used: must be rewritten for EF Core.", "Move to DbContext APIs.",
                         file_override="(solution)", line_override=0, snippet="")
            if self.flavour == "EF Core" and (self.major or 0) < 10 <= self.target and re.search(r"\.Contains\s*\(\s*\w+\s*\.\s*\w+\s*\)", self.repo_text):
                self.add("EF808", None, 0, "Collection Contains translation changes in EF Core 10 (multiple parameters instead of OPENJSON).",
                         "Compare SQL/plans for queries with large Contains lists after upgrading.", file_override="(solution)", line_override=0, snippet="")

    # -- run
    def run(self):
        self.load()
        self.discover_ctx()
        self.global_notracking = self.global_has(r"UseQueryTrackingBehavior\s*\(\s*QueryTrackingBehavior\s*\.\s*NoTracking")
        self.global_split = self.global_has(r"UseQuerySplittingBehavior\s*\(\s*QuerySplittingBehavior\s*\.\s*SplitQuery")
        for f in self.files:
            self.rules_code(f)
        self.rules_entities()
        self.rules_migrations()
        self.rules_config()
        self.rules_tests()
        self.rules_project()
        self.rules_upgrade()
        # dedupe + cap
        seen, out, per = set(), [], {}
        for x in self.findings:
            key = (x["id"], x["file"], x["line"])
            if key in seen:
                continue
            seen.add(key)
            per[x["id"]] = per.get(x["id"], 0) + 1
            if per[x["id"]] > self.max_per_rule:
                continue
            out.append(x)
        out.sort(key=lambda x: (SEV_ORDER.index(x["severity"]), x["id"], x["file"] or "", x["line"] or 0))
        self.findings = out
        return self.result(per)

    def result(self, per):
        counts = {s: sum(1 for x in self.findings if x["severity"] == s) for s in SEV_ORDER}
        penalty = sum(WEIGHTS[x["severity"]] for x in self.findings)
        health = max(0, round(100 - penalty))
        capped = {k: v for k, v in per.items() if v > self.max_per_rule}
        return {
            "meta": {"root": str(self.root), "scanned_files": len(self.files), "test_files": len(self.test_files),
                     "flavour": self.flavour, "ef_major": self.major, "target_version": self.target,
                     "context_types": self.ctx_types, "date": date.today().isoformat(),
                     "note": "Heuristic candidates. Verify each by reading the code; recompute health after dropping false positives."},
            "projects": self.detect["projects"],
            "summary": {"counts": counts, "health_score": health, "total": len(self.findings),
                        "capped_rules": capped},
            "findings": self.findings,
        }


def to_md(res):
    m, s = res["meta"], res["summary"]
    lines = [f"# EF scan (candidates) for `{m['root']}`", "",
             f"Detected: **{m['flavour']} {m['ef_major']}** | target: {m['target_version'] or '-'} | files: {m['scanned_files']} | "
             f"DbContexts: {', '.join(m['context_types']) or 'none found'}", "",
             f"**Health (unverified): {s['health_score']}/100** | " + ", ".join(f"{k}: {v}" for k, v in s["counts"].items()), "",
             "> " + m["note"], ""]
    if s["capped_rules"]:
        lines += [f"Capped rules (more hits than shown): {s['capped_rules']}", ""]
    lines += ["| Sev | ID | Where | Finding | Conf |", "|---|---|---|---|---|"]
    for x in res["findings"]:
        where = f"{x['file']}:{x['line']}" if x["line"] else x["file"]
        lines.append(f"| {x['severity']} | {x['id']} | `{where}` | {x['message'].replace('|', '/')} | {x['confidence']} |")
    lines += ["", "## Fix hints", ""]
    for rid in sorted({x["id"] for x in res["findings"]}):
        ex = next(x for x in res["findings"] if x["id"] == rid)
        lines.append(f"- **{rid} {ex['title']}**: {ex['fix']} ({ex['reference']})")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="EF review scanner (candidates)")
    ap.add_argument("root")
    ap.add_argument("--format", choices=["json", "md"], default="md")
    ap.add_argument("--out")
    ap.add_argument("--ef-version", type=int, help="force EF Core major (e.g. 8); 6 means EF6")
    ap.add_argument("--target-version", type=int, help="EF Core major you plan to upgrade to (enables upgrade rules)")
    ap.add_argument("--include-tests", action="store_true")
    ap.add_argument("--max-per-rule", type=int, default=50)
    a = ap.parse_args()
    sc = Scanner(a.root, a.ef_version, a.target_version, a.include_tests, a.max_per_rule)
    if a.ef_version == 6:
        sc.flavour, sc.major = "EF6", 6
    res = sc.run()
    out = json.dumps(res, indent=2) if a.format == "json" else to_md(res)
    if a.out:
        Path(a.out).write_text(out, encoding="utf-8")
        s = res["summary"]
        print(f"Wrote {a.out}: {s['total']} candidates, health {s['health_score']}/100, {s['counts']}")
    else:
        print(out)


if __name__ == "__main__":
    main()
