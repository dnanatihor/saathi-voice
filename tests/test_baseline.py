"""Phase 0 repository baseline from SPEC.md Appendix B.1."""

from pathlib import Path

from saathi.paths import REPO_ROOT

CI_COMMANDS = (
    "uv sync --locked --all-groups",
    "uv run ruff check .",
    "uv run ruff format --check .",
    "uv run mypy",
    "uv run pytest",
)


def test_baseline_files_exist() -> None:
    required = [
        "README.md",
        "CHANGELOG.md",
        "LICENSE",
        ".gitignore",
        "pyproject.toml",
        ".pre-commit-config.yaml",
        ".github/workflows/ci.yml",
        "docs/adr/0000-template.md",
    ]
    missing = [name for name in required if not (REPO_ROOT / name).is_file()]
    assert missing == []


def test_readme_stub_has_name_why_and_planned_quickstart() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert readme.startswith("# Saathi Voice — ")
    assert "## Why" in readme
    assert "TODO" not in readme.split("## Quickstart", maxsplit=1)[0]
    why = readme.split("## Why", maxsplit=1)[1].split("##", maxsplit=1)[0].strip()
    assert len(why) > 80
    assert "## Quickstart" in readme
    assert "Planned" in readme
    for command in CI_COMMANDS:
        assert command in readme
    assert "CI" in readme
    assert "Apache-2.0" in readme


def test_changelog_has_unreleased_section() -> None:
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [Unreleased]" in changelog
    assert "Keep a Changelog" in changelog


def test_ci_workflow_runs_tooling() -> None:
    workflow = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    for command in CI_COMMANDS:
        assert command in workflow
    assert "web/" not in workflow


def test_license_is_apache() -> None:
    license_text = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "Apache License" in license_text
    assert Path(REPO_ROOT / "LICENSE").is_file()
