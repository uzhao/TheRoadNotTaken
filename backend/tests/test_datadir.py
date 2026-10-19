"""数据目录初始化：首次启动复制种子骨架、建立空状态文件、初始化 git 并提交；再次启动不覆盖。"""

import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from theroadnottaken.app import create_app
from theroadnottaken.cli import main as cli_main


def start_fails(data_dir: Path, capsys: pytest.CaptureFixture[str]) -> str:
    """用命令行入口启动，断言非零退出，返回 stderr。

    `--static-dir` 指向数据目录只是为了不依赖仓库里是否有前端构建产物；启动在校验阶段就失败，
    不会真的监听端口。
    """
    with pytest.raises(SystemExit) as exit_info:
        cli_main(["--data-dir", str(data_dir), "--static-dir", str(data_dir)])
    assert exit_info.value.code == 1
    return capsys.readouterr().err


def git(data_dir: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(data_dir), *args], check=True, capture_output=True, text=True
    ).stdout


def test_first_start_initializes_data_dir(
    client: TestClient, data_dir: Path, sample_skeleton: Path
) -> None:
    assert client.get("/api/health").status_code == 200

    assert (data_dir / "skeleton.yaml").read_text(encoding="utf-8") == sample_skeleton.read_text(
        encoding="utf-8"
    )
    assert json.loads((data_dir / "state.json").read_text(encoding="utf-8")) == {}
    assert json.loads((data_dir / "conversations.json").read_text(encoding="utf-8")) == {}
    assert (data_dir / "proposals.yaml").is_file()
    assert (data_dir / ".git").is_dir()

    # 生成任务目录被 git 忽略
    (data_dir / "jobs" / "job-1").mkdir(parents=True)
    (data_dir / "jobs" / "job-1" / "agy.ndjson").write_text("{}", encoding="utf-8")
    assert git(data_dir, "status", "--porcelain") == ""

    # 首个提交包含全部文件，提交信息人可读
    log = git(data_dir, "log", "--format=%s")
    assert log.strip().count("\n") == 0
    assert "初始化数据目录" in log
    tracked = set(git(data_dir, "ls-files").split())
    assert tracked == {
        ".gitignore",
        "skeleton.yaml",
        "state.json",
        "conversations.json",
        "proposals.yaml",
    }


def test_restart_does_not_overwrite_existing_files(
    client: TestClient, data_dir: Path, sample_skeleton: Path
) -> None:
    # 学习者手改了骨架（加一个别名）和状态，再写了一份提议
    skeleton_text = (data_dir / "skeleton.yaml").read_text(encoding="utf-8") + "# 手改标记\n"
    (data_dir / "skeleton.yaml").write_text(skeleton_text, encoding="utf-8")
    state_text = json.dumps(
        {
            "c01-logic-and-proof": {
                "status": "mastered",
                "weak_points": [],
                "verifications": [],
                "updated_at": "2026-10-01T10:00:00Z",
            }
        }
    )
    (data_dir / "state.json").write_text(state_text, encoding="utf-8")
    (data_dir / "proposals.yaml").write_text("- {id: p1}\n", encoding="utf-8")
    commits_before = git(data_dir, "rev-list", "--count", "HEAD")

    with TestClient(create_app(data_dir=data_dir, seed_skeleton=sample_skeleton)) as again:
        assert again.get("/api/health").status_code == 200

    assert (data_dir / "skeleton.yaml").read_text(encoding="utf-8") == skeleton_text
    assert (data_dir / "state.json").read_text(encoding="utf-8") == state_text
    assert (data_dir / "proposals.yaml").read_text(encoding="utf-8") == "- {id: p1}\n"
    assert git(data_dir, "rev-list", "--count", "HEAD") == commits_before


def test_deleted_file_is_restored_without_committing_hand_edits(
    client: TestClient, data_dir: Path, sample_skeleton: Path
) -> None:
    (data_dir / "conversations.json").unlink()
    (data_dir / "state.json").write_text("{ }", encoding="utf-8")  # 学习者未提交的手改
    commits_before = git(data_dir, "rev-list", "--count", "HEAD")

    with TestClient(create_app(data_dir=data_dir, seed_skeleton=sample_skeleton)):
        pass

    assert (data_dir / "conversations.json").read_text(encoding="utf-8") == "{}\n"
    assert (data_dir / "state.json").read_text(encoding="utf-8") == "{ }"
    # 恢复的文件与 HEAD 一致，无需新提交；手改仍留在工作树里，不被顺手提交
    assert git(data_dir, "rev-list", "--count", "HEAD") == commits_before
    assert git(data_dir, "status", "--porcelain").strip() == "M state.json"


def test_hand_made_repo_gets_missing_files_committed_separately(
    data_dir: Path, sample_skeleton: Path
) -> None:
    (data_dir / "skeleton.yaml").write_text(sample_skeleton.read_text(encoding="utf-8"))
    git(data_dir, "init", "--quiet")
    git(data_dir, "add", "skeleton.yaml")
    git(data_dir, "-c", "user.name=me", "-c", "user.email=me@x", "commit", "-q", "-m", "手建")
    (data_dir / "skeleton.yaml").write_text(
        sample_skeleton.read_text(encoding="utf-8") + "# 手改\n", encoding="utf-8"
    )

    with TestClient(create_app(data_dir=data_dir, seed_skeleton=sample_skeleton)):
        pass

    subjects = git(data_dir, "log", "--format=%s").split("\n")
    assert (
        subjects[0]
        == "补齐数据目录缺失的文件：state.json、conversations.json、proposals.yaml、.gitignore"
    )
    assert subjects[1] == "手建"
    assert git(data_dir, "status", "--porcelain").strip() == "M skeleton.yaml"


def test_existing_dir_without_git_gets_repo_with_its_files_in_first_commit(
    data_dir: Path, sample_skeleton: Path
) -> None:
    (data_dir / "skeleton.yaml").write_text(sample_skeleton.read_text(encoding="utf-8"))
    (data_dir / "notes.md").write_text("我的笔记\n", encoding="utf-8")

    with TestClient(create_app(data_dir=data_dir, seed_skeleton=sample_skeleton)):
        pass

    assert git(data_dir, "log", "--format=%s").strip() == "初始化数据目录"
    assert "notes.md" in git(data_dir, "ls-files").split()


def test_invalid_skeleton_refuses_to_start_and_points_at_location(
    data_dir: Path, sample_skeleton: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    text = sample_skeleton.read_text(encoding="utf-8").replace(
        "prerequisites: [c02-function-limit-continuity]", "prerequisites: [c02-nope]"
    )
    (data_dir / "skeleton.yaml").write_text(text, encoding="utf-8")

    err = start_fails(data_dir, capsys)
    assert "拒绝启动" in err
    assert "主题 c02-derivative-definition：前置 c02-nope 不存在" in err
    assert "第 " in err  # 带行号


def test_invalid_state_file_refuses_to_start(
    client: TestClient, data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (data_dir / "state.json").write_text(
        json.dumps(
            {"c01-logic-and-proof": {"status": "done", "updated_at": "2026-10-01T10:00:00Z"}}
        ),
        encoding="utf-8",
    )
    err = start_fails(data_dir, capsys)
    assert "状态文件不合法" in err
    assert "c01-logic-and-proof.status" in err

    (data_dir / "state.json").write_text("{not json", encoding="utf-8")
    assert "JSON 语法错误" in start_fails(data_dir, capsys)
