"""Offline harness for the feature workflow's manual-dispatch input handling.

The tests execute the exact ``run:`` script from ``.github/workflows/features.yml``
with a stub ``python`` earlier on ``PATH``. No real pipeline, database, network
call or credential is touched: the stub only records its argv.
"""
from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import pytest

WORKFLOW = Path(".github/workflows/features.yml")
RUN_STEP_NAME = "Run explicit feature pipeline"
BASE_ARGV = ["main.py", "features", "--mode"]

STUB = """#!/bin/bash
set -euo pipefail
: > "$ARGV_LOG"
for arg in "$@"; do
  printf '%s\\0' "$arg" >> "$ARGV_LOG"
done
exit "${STUB_EXIT_CODE:-0}"
"""


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _run_script() -> str:
    """Extract and dedent the workflow's single feature run block."""
    lines = _workflow_text().splitlines()
    step = next(
        (i for i, line in enumerate(lines) if line.strip() == f"- name: {RUN_STEP_NAME}"),
        None,
    )
    assert step is not None, f"workflow step {RUN_STEP_NAME!r} not found"
    run_index = next(
        i for i in range(step, len(lines)) if lines[i].strip() == "run: |"
    )
    body = lines[run_index + 1:]
    first = next(line for line in body if line.strip())
    indent = len(first) - len(first.lstrip())
    script = []
    for line in body:
        if line.strip() and len(line) - len(line.lstrip()) < indent:
            break
        script.append(line[indent:] if line.strip() else "")
    return "\n".join(script).rstrip("\n") + "\n"


def _run(
    tmp_path: Path,
    inputs: dict[str, str],
    *,
    stub_exit: int = 0,
    work_files: dict[str, str] | None = None,
):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "python"
    stub.write_text(STUB, encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    argv_log = tmp_path / "argv.log"
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    for name, content in (work_files or {}).items():
        (work_dir / name).write_text(content, encoding="utf-8")

    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "HOME": str(tmp_path / "home"),
        "ARGV_LOG": str(argv_log),
        "STUB_EXIT_CODE": str(stub_exit),
    }
    env.update(inputs)

    proc = subprocess.run(
        ["/bin/bash", "-c", _run_script()],
        cwd=work_dir,
        env=env,
        capture_output=True,
        text=True,
    )

    argv: list[str] = []
    if argv_log.exists():
        raw = argv_log.read_bytes()
        assert raw.endswith(b"\0"), "stub python must record NUL-separated argv"
        argv = [chunk.decode("utf-8") for chunk in raw.split(b"\0")[:-1]]
    return proc, argv, work_dir


def test_valid_inputs_are_passed_as_quoted_arrays(tmp_path):
    proc, argv, _ = _run(
        tmp_path,
        {
            "MODE_INPUT": "incremental",
            "DATE_INPUT": "05/11/2026",
            "SYMBOLS_INPUT": "SSI HPG",
            "TIMEFRAMES_INPUT": "15m 1d",
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert argv == BASE_ARGV + [
        "incremental",
        "--date",
        "05/11/2026",
        "--symbols",
        "SSI",
        "HPG",
        "--timeframes",
        "15m",
        "1d",
    ]


@pytest.mark.parametrize("blank", ["", "   ", "\t", " \t  "])
def test_blank_optional_inputs_omit_their_flags(tmp_path, blank):
    proc, argv, _ = _run(
        tmp_path,
        {
            "MODE_INPUT": "full",
            "DATE_INPUT": blank,
            "SYMBOLS_INPUT": blank,
            "TIMEFRAMES_INPUT": blank,
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert argv == BASE_ARGV + ["full"]
    assert "--date" not in argv
    assert "--symbols" not in argv
    assert "--timeframes" not in argv


@pytest.mark.parametrize("mode", [None, "", "   ", "\t"])
def test_blank_mode_falls_back_to_existing_incremental_default(tmp_path, mode):
    inputs = {"DATE_INPUT": "", "SYMBOLS_INPUT": "", "TIMEFRAMES_INPUT": ""}
    if mode is not None:
        inputs["MODE_INPUT"] = mode
    proc, argv, _ = _run(tmp_path, inputs)
    assert proc.returncode == 0, proc.stderr
    assert argv == BASE_ARGV + ["incremental"]


def test_symbols_and_timeframes_split_on_spaces_and_tabs(tmp_path):
    proc, argv, _ = _run(
        tmp_path,
        {
            "MODE_INPUT": "full",
            "DATE_INPUT": "",
            "SYMBOLS_INPUT": "SSI\tHPG   VNM",
            "TIMEFRAMES_INPUT": "15m\t60m",
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert argv == BASE_ARGV + [
        "full",
        "--symbols",
        "SSI",
        "HPG",
        "VNM",
        "--timeframes",
        "15m",
        "60m",
    ]


def test_shell_metacharacters_stay_literal_argv_data(tmp_path):
    symbols = 'SSI;touch pwned $HOME $(id) `whoami` * a"b c\'d'
    proc, argv, work_dir = _run(
        tmp_path,
        {
            "MODE_INPUT": "incremental",
            "DATE_INPUT": "05/11/2026",
            "SYMBOLS_INPUT": symbols,
            "TIMEFRAMES_INPUT": "1d",
        },
    )
    assert proc.returncode == 0, proc.stderr
    start = argv.index("--symbols") + 1
    assert argv[start:argv.index("--timeframes")] == [
        "SSI;touch",
        "pwned",
        "$HOME",
        "$(id)",
        "`whoami`",
        "*",
        'a"b',
        "c'd",
    ]
    # No command substitution, glob expansion or side effect ran in the work dir.
    assert not (work_dir / "pwned").exists()
    assert sorted(p.name for p in work_dir.iterdir()) == []


def test_glob_token_is_not_expanded_into_matching_files(tmp_path):
    proc, argv, _ = _run(
        tmp_path,
        {
            "MODE_INPUT": "incremental",
            "DATE_INPUT": "",
            "SYMBOLS_INPUT": "*",
            "TIMEFRAMES_INPUT": "",
        },
        work_files={"canary.txt": "canary"},
    )
    assert proc.returncode == 0, proc.stderr
    assert argv == BASE_ARGV + ["incremental", "--symbols", "*"]


def test_date_is_one_literal_argument(tmp_path):
    date = "05/11/2026;echo hacked $(id) `id`"
    proc, argv, _ = _run(
        tmp_path,
        {
            "MODE_INPUT": "incremental",
            "DATE_INPUT": date,
            "SYMBOLS_INPUT": "",
            "TIMEFRAMES_INPUT": "",
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert argv == BASE_ARGV + ["incremental", "--date", date]


@pytest.mark.parametrize(
    "overrides",
    [
        {"SYMBOLS_INPUT": "SSI --mode full"},
        {"SYMBOLS_INPUT": "-rf"},
        {"SYMBOLS_INPUT": "--symbols"},
        {"TIMEFRAMES_INPUT": "1d --symbols SSI"},
        {"TIMEFRAMES_INPUT": "--"},
        {"DATE_INPUT": "--mode"},
        {"MODE_INPUT": "-full"},
    ],
)
def test_option_like_tokens_are_rejected_before_python(tmp_path, overrides):
    inputs = {
        "MODE_INPUT": "incremental",
        "DATE_INPUT": "",
        "SYMBOLS_INPUT": "",
        "TIMEFRAMES_INPUT": "",
    }
    inputs.update(overrides)
    proc, argv, _ = _run(tmp_path, inputs)
    assert proc.returncode != 0
    assert "::error::" in proc.stderr
    assert "option-like token" in proc.stderr
    assert argv == []


@pytest.mark.parametrize(
    "name,value",
    [
        ("DATE_INPUT", "05/11/2026\r"),
        ("DATE_INPUT", "05/11/2026\nfull"),
        ("SYMBOLS_INPUT", "SSI\rHPG"),
        ("SYMBOLS_INPUT", "SSI\n--mode"),
        ("SYMBOLS_INPUT", "\r"),
        ("TIMEFRAMES_INPUT", "1d\n--mode full"),
        ("MODE_INPUT", "incremental\nfull"),
    ],
)
def test_cr_or_lf_is_rejected_before_array_splitting(tmp_path, name, value):
    inputs = {
        "MODE_INPUT": "incremental",
        "DATE_INPUT": "",
        "SYMBOLS_INPUT": "",
        "TIMEFRAMES_INPUT": "",
    }
    inputs[name] = value
    proc, argv, _ = _run(tmp_path, inputs)
    assert proc.returncode != 0
    assert "::error::" in proc.stderr
    assert "CR or LF" in proc.stderr
    assert argv == []


def test_python_exit_code_is_propagated(tmp_path):
    proc, argv, _ = _run(
        tmp_path,
        {
            "MODE_INPUT": "full",
            "DATE_INPUT": "",
            "SYMBOLS_INPUT": "",
            "TIMEFRAMES_INPUT": "",
        },
        stub_exit=7,
    )
    assert proc.returncode == 7
    assert argv == BASE_ARGV + ["full"]


def test_run_script_has_no_inline_input_expressions_or_eval():
    script = _run_script()
    assert "${{" not in script
    assert " eval " not in script and "\neval " not in script
    assert 'read -r -a symbols <<< "$SYMBOLS_INPUT"' in script
    assert 'read -r -a timeframes <<< "$TIMEFRAMES_INPUT"' in script
    assert 'cmd+=(--symbols "${symbols[@]}")' in script
    assert 'cmd+=(--timeframes "${timeframes[@]}")' in script
    assert '"${cmd[@]}"' in script
    # Never emit the optional flags without values.
    assert "cmd+=(--symbols)" not in script
    assert "cmd+=(--timeframes)" not in script
    assert "cmd+=(--symbols $SYMBOLS_INPUT" not in script
    assert "cmd+=(--timeframes $TIMEFRAMES_INPUT" not in script


def test_workflow_keeps_command_defaults_and_credentials():
    text = _workflow_text()
    assert "workflow_dispatch:" in text
    assert "python main.py features" in text
    assert 'default: "incremental"' in text
    assert "- incremental" in text and "- full" in text
    assert 'default: "15m 60m 1d"' in text
    assert 'python-version: "3.11"' in text
    assert "SUPABASE_URL: ${{ secrets.SUPABASE_URL }}" in text
    assert "SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}" in text
    assert "DATE_INPUT: ${{ inputs.date }}" in text
    assert "MODE_INPUT: ${{ inputs.mode }}" in text
    assert "SYMBOLS_INPUT: ${{ inputs.symbols }}" in text
    assert "TIMEFRAMES_INPUT: ${{ inputs.timeframes }}" in text
