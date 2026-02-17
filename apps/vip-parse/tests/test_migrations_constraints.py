from __future__ import annotations

import ast
import importlib.util
import re
from pathlib import Path
from types import ModuleType


APP_ROOT = Path(__file__).resolve().parents[1]
VERSIONS_DIR = APP_ROOT / "alembic" / "versions"
REPO_ROOT = APP_ROOT.parents[1]


def _migration_paths() -> list[Path]:
    return sorted(
        p
        for p in VERSIONS_DIR.glob("*.py")
        if p.is_file() and not p.name.startswith("__")
    )


def _load_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load migration module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_revision_ids_are_unique() -> None:
    revisions: list[str] = []
    for path in _migration_paths():
        module = _load_module(path)
        revision = getattr(module, "revision", None)
        assert isinstance(revision, str) and revision, f"{path.name} missing valid revision id"
        revisions.append(revision)

    assert len(revisions) == len(set(revisions)), "Duplicate Alembic revision ids detected"


def test_migration_chain_is_linear_with_single_head() -> None:
    modules = [_load_module(path) for path in _migration_paths()]
    by_revision = {m.revision: m for m in modules}

    children_count: dict[str, int] = {rev: 0 for rev in by_revision}
    roots = 0
    for module in modules:
        down_revision = getattr(module, "down_revision", None)
        if down_revision is None:
            roots += 1
            continue
        assert isinstance(down_revision, str), (
            f"{module.revision} has non-linear down_revision {down_revision!r}; "
            "this project expects a single linear migration chain"
        )
        assert down_revision in by_revision, (
            f"{module.revision} references unknown down_revision {down_revision}"
        )
        children_count[down_revision] += 1

    heads = [rev for rev, count in children_count.items() if count == 0]
    assert roots == 1, f"Expected exactly one root migration, found {roots}"
    assert len(heads) == 1, f"Expected exactly one head migration, found {len(heads)}"


def test_migration_modules_define_upgrade_and_downgrade() -> None:
    for path in _migration_paths():
        module = _load_module(path)
        assert callable(getattr(module, "upgrade", None)), f"{path.name} missing upgrade()"
        assert callable(getattr(module, "downgrade", None)), f"{path.name} missing downgrade()"


def test_non_nullable_add_column_operations_define_server_default() -> None:
    """
    Constraint: adding NOT NULL columns must include server_default.

    This prevents runtime failures when migrations run against populated tables.
    """
    offenders: list[str] = []
    for path in _migration_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "op"
                and func.attr == "add_column"
            ):
                continue
            if len(node.args) < 2 or not isinstance(node.args[1], ast.Call):
                continue
            col_call = node.args[1]
            col_func = col_call.func
            if not (
                isinstance(col_func, ast.Attribute)
                and isinstance(col_func.value, ast.Name)
                and col_func.value.id == "sa"
                and col_func.attr == "Column"
            ):
                continue

            kw = {k.arg: k.value for k in col_call.keywords if k.arg}
            nullable_false = isinstance(kw.get("nullable"), ast.Constant) and kw["nullable"].value is False
            has_server_default = "server_default" in kw
            if nullable_false and not has_server_default:
                offenders.append(path.name)

    assert not offenders, (
        "Found op.add_column(... nullable=False) without server_default in: "
        + ", ".join(sorted(set(offenders)))
    )


def test_render_web_start_command_runs_alembic_upgrade_head() -> None:
    render_file = REPO_ROOT / "render.yaml"
    assert render_file.exists(), "render.yaml not found at repo root"
    text = render_file.read_text(encoding="utf-8")

    pattern = re.compile(
        r"name:\s*vip30-web[\s\S]*?startCommand:\s*\|[\s\S]*?alembic upgrade head",
        re.IGNORECASE,
    )
    assert pattern.search(text), "vip30-web startCommand must run `alembic upgrade head`"
