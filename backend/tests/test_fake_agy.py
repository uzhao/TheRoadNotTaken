"""假 agy 本身：后续工单要用的故障形态（越界写、超大文件、flag 误用）在这里直接验证。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import agy_steps as s
from conftest import FakeAgy


def call_agy(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["agy", *args], cwd=cwd, capture_output=True, text=True, timeout=30)


def test_writes_files_in_cwd_including_escaping_paths_and_oversized_files(
    fake_agy: FakeAgy, tmp_path: Path
) -> None:
    job = tmp_path / "job"
    job.mkdir()
    fake_agy.script(
        s.run(
            s.init(),
            s.write("figures/tangent.svg", "<svg/>"),
            s.write("../escaped.txt", "out"),
            s.write("figures/huge.png", size=600 * 1024),
            s.result(),
        )
    )

    proc = call_agy(job, "--output-format", "stream-json", "--print=画图")

    assert proc.returncode == 0
    assert (job / "figures" / "tangent.svg").read_text() == "<svg/>"
    assert (tmp_path / "escaped.txt").read_text() == "out"
    assert (job / "figures" / "huge.png").stat().st_size == 600 * 1024


def test_records_command_line_prompt_and_cwd(fake_agy: FakeAgy, tmp_path: Path) -> None:
    call_agy(tmp_path, "--conversation", "conv-9", "--effort=high", "--print=继续")

    (call,) = fake_agy.calls()
    assert call["conversation"] == "conv-9"
    assert call["effort"] == "high"
    assert call["prompt"] == "继续"
    assert call["cwd"] == str(tmp_path)


def test_print_flag_swallowing_next_flag_is_an_error_like_real_agy(
    fake_agy: FakeAgy, tmp_path: Path
) -> None:
    proc = call_agy(tmp_path, "-p", "--output-format", "json", "OK")

    assert proc.returncode == 1
    assert "took" in proc.stderr


def test_denied_actions_scenario_writes_jetski_line_and_result_field(
    fake_agy: FakeAgy, tmp_path: Path
) -> None:
    fake_agy.script(s.denied())

    proc = call_agy(tmp_path, "--output-format", "stream-json", "--print=画图")

    assert proc.returncode == 0
    assert "auto-denied" in proc.stderr
    result = json.loads(proc.stdout.splitlines()[-1])
    assert result["event"] == "result"
    assert result["denied_actions"][0]["action"] == "command"
