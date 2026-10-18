"""The documentation's runnable examples, executed as written.

The first code a new user runs is extracted from its Markdown file and executed on the
``fake``, so none of it can drift from the bridge: the README's quick start, the
getting-started application, and the testing guide's unit-test example
(docs/getting-started.md "Your first application"; docs/guides/testing.md "Unit tests").
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def _first_python_block(path: Path, heading: str) -> str:
    """The first fenced ``python`` block under the Markdown ``heading`` of ``path``."""
    text = path.read_text(encoding="utf-8")
    start = text.index(f"\n{heading}\n")
    match = re.search(r"```python\n(.*?)```", text[start:], re.DOTALL)
    assert match is not None, f"no python block under {heading!r} in {path}"
    return match.group(1)


def _run_as_main(path: Path, heading: str, capsys: Any) -> str:
    """Execute the block as a script and return what it printed."""
    code = _first_python_block(path, heading)
    assert "asyncio.run(main())" in code  # the block runs a whole session
    exec(compile(code, path.name, "exec"), {"__name__": "__main__"})  # noqa: S102
    return capsys.readouterr().out


def test_the_readme_quick_start_runs_on_the_fake(capsys) -> None:
    out = _run_as_main(ROOT / "README.md", "## Quick start", capsys)
    # It printed the fake's dances, and the first one is a dance the fake can play.
    assert "'eagle-dance'" in out


def test_the_getting_started_application_prints_what_the_page_says(capsys) -> None:
    out = _run_as_main(
        ROOT / "docs" / "getting-started.md", "## Your first application", capsys
    )
    page = (ROOT / "docs" / "getting-started.md").read_text(encoding="utf-8")
    shown = re.search(r"It prints:\n\n```\n(.*?)```", page, re.DOTALL)
    assert shown is not None
    assert out == shown.group(1)


def test_the_testing_guide_unit_example_passes() -> None:
    code = _first_python_block(
        ROOT / "docs" / "guides" / "testing.md", "## Unit tests: the `fake` backend"
    )
    namespace: dict[str, Any] = {"__name__": "docs_example"}
    exec(compile(code, "testing.md", "exec"), namespace)  # noqa: S102
    tests = [v for k, v in namespace.items() if k.startswith("test_") and callable(v)]
    assert len(tests) == 1, "the guide's example defines one test"
    tests[0]()
