#!/usr/bin/env python3
"""
verification_guard.py — Claude Code PreToolUse hook

検証ループ(IMPL_RULES R-9)の「報酬ハック」を防ぐ安全弁。
実装エージェントが lint/type/test を green にするために、
テストそのものを弱める/消す行為を検出する。

検出対象(テストファイルに対する Write/Edit/MultiEdit):
- テスト関数/ケースの削除          (Edit: old に存在し new で消えた)
- アサーションの削除               (Edit: old のアサーション数 > new)
- skip / xfail / only の新規付与    (Edit/Write: 新規に skip 系マーカーが増えた)

判定対象ファイル(いずれか):
- パスに /tests/ または /test/ を含む
- ファイル名が test_*.py / *_test.py / *.test.* / *.spec.*

デフォルトは警告(exit 1)。環境変数 IMPL_VERIFICATION_STRICT=1 でブロック(exit 2)。

対応ルール: IMPL_RULES R-9.2 / §4.4 G-5 / §6 失敗パターン。
誤検出時: テストを正当に削除/整理したい場合は STRICT を外すか、
spec_gaps.md に理由を記録してから実施する。
"""
from __future__ import annotations

import json
import os
import re
import sys

# --- 検出パターン --------------------------------------------------------

# skip / xfail / only 系（テストを実行しない/単独実行に絞る = 検証の無効化）
SKIP_PATTERNS = [
    r"@pytest\.mark\.skip\b",
    r"@pytest\.mark\.xfail\b",
    r"\bpytest\.skip\s*\(",
    r"@unittest\.skip\b",
    r"\.skip\s*\(",
    r"\.only\s*\(",
    r"\bxit\s*\(",
    r"\bxdescribe\s*\(",
    r"\bfit\s*\(",       # jasmine/jest focused
    r"\bfdescribe\s*\(",
]
SKIP_RE = re.compile("|".join(SKIP_PATTERNS))

# アサーション（テストの「検証する力」そのもの）
ASSERT_PATTERNS = [
    r"\bassert\b",
    r"\bself\.assert\w+\s*\(",
    r"\bpytest\.raises\s*\(",
    r"\bexpect\s*\(",
    r"\.should\b",
    r"\bchai\b",
]
ASSERT_RE = re.compile("|".join(ASSERT_PATTERNS))

# テスト関数/ケースの宣言
TESTDEF_PATTERNS = [
    r"\bdef\s+test_\w+",
    r"\bit\s*\(",
    r"\btest\s*\(",
    r"\bdescribe\s*\(",
]
TESTDEF_RE = re.compile("|".join(TESTDEF_PATTERNS))

TEST_EXTS = (".py", ".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte")


def _normalize(p: str) -> str:
    return p.replace("\\", "/")


def _is_test_file(fp: str) -> bool:
    f = _normalize(fp)
    if not f.endswith(TEST_EXTS):
        return False
    parts = f.split("/")
    if any(p in {"tests", "test", "__tests__"} for p in parts):
        return True
    base = parts[-1]
    if base.startswith("test_") or base.endswith("_test.py"):
        return True
    if ".test." in base or ".spec." in base:
        return True
    return False


def _count(rx: re.Pattern, text: str) -> int:
    return len(rx.findall(text or ""))


def _gather_edit_pairs(ti: dict) -> list[tuple[str, str]]:
    """Edit / MultiEdit から (old, new) のペア群を取り出す。"""
    pairs: list[tuple[str, str]] = []
    if "edits" in ti and isinstance(ti["edits"], list):
        for e in ti["edits"]:
            pairs.append((e.get("old_string") or "", e.get("new_string") or ""))
    else:
        old = ti.get("old_string")
        new = ti.get("new_string")
        if old is not None or new is not None:
            pairs.append((old or "", new or ""))
    return pairs


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0  # fail-open（他フックと同様）

    tool = data.get("tool_name", "")
    if tool not in {"Write", "Edit", "MultiEdit"}:
        return 0

    ti = data.get("tool_input", {}) or {}
    fp = ti.get("file_path") or ti.get("path") or ""
    if not fp or not _is_test_file(fp):
        return 0

    findings: list[str] = []

    if tool == "Write":
        # Write は旧内容を持たないため、新規に skip/only を「入れている」ことだけ検出
        content = ti.get("content") or ti.get("text") or ""
        if SKIP_RE.search(content):
            findings.append(
                "skip / xfail / only マーカーを含むテストを書き込もうとしています"
                "（テストの無効化・単独実行への絞り込み）。"
            )
    else:
        for old, new in _gather_edit_pairs(ti):
            # skip/only の新規付与
            if _count(SKIP_RE, new) > _count(SKIP_RE, old):
                findings.append("skip / xfail / only マーカーを追加しています（テストの無効化）。")
            # アサーションの削除
            removed_asserts = _count(ASSERT_RE, old) - _count(ASSERT_RE, new)
            if removed_asserts > 0:
                findings.append(f"アサーションを {removed_asserts} 件削除しています（検証の弱体化）。")
            # テスト宣言の削除
            removed_tests = _count(TESTDEF_RE, old) - _count(TESTDEF_RE, new)
            if removed_tests > 0:
                findings.append(f"テストケース/関数を {removed_tests} 件削除しています。")

    if not findings:
        return 0

    strict = os.environ.get("IMPL_VERIFICATION_STRICT", "0") == "1"
    print("[verification_guard] 検証ループの報酬ハックの疑い（テストの弱体化）を検出。", file=sys.stderr)
    print(f"  対象: {fp}", file=sys.stderr)
    for f in findings:
        print(f"  - {f}", file=sys.stderr)
    print(
        "  対応: テストを弱めて green を作るのは禁止（R-9.2 / §4.4 G-5）。"
        "テストが仕様と食い違って落ちる場合は、テストを消さず docs/_impl_state/spec_gaps.md に起票してください。",
        file=sys.stderr,
    )
    print("  正当な削除/整理なら IMPL_VERIFICATION_STRICT を外して再実行してください。", file=sys.stderr)
    return 2 if strict else 1


if __name__ == "__main__":
    sys.exit(main())
