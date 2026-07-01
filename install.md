# インストール手順

このエージェント群を使うには2つの方法があります。

## 方法A: プラグインとして使う（推奨）

Claude Code / Cowork にプラグインとしてインストールするだけで:

- `agents/` のサブエージェント（設計10体 + 実装9体 + インフラ4体 infra-orchestrator/infra-architect/terraform-generator/deployment-engineer + メタ改善1体 retrospective）
- `references/`（SPEC_RULES / IMPL_RULES / INFRA_RULES — エージェントが起動時に Read する共通ルール）
- `skills/`（requirements-architect / security-review / spec-traceability）
- `hooks/hooks.json` の安全弁（シークレット / PII / docs read-only / @spec / フォーマット）

が **自動で有効** になります。追加の配置作業は不要です（プロジェクト側の `docs/_state/` 等は各エージェントが必要時にテンプレートから作成します）。

> ℹ️ hooks は `python` コマンドを呼びます（Python 3.10+）。macOS / Linux で `python` が無い場合は、方法B の手動配置で `python3` 指定に置き換えてください。

---

## 方法B: 手動コピーで使う

プラグインを使わず、設計対象プロジェクトに直接配置するパターンです。

### macOS / Linux

```bash
# このリポジトリのフルパス
SRC="<このフォルダの絶対パス>"

# サブエージェント (設計 + 実装)
mkdir -p .claude/agents
cp "$SRC"/agents/*.md .claude/agents/

# 共通ルール（エージェントが起動時に Read する）
mkdir -p .claude/references
cp "$SRC"/references/*.md .claude/references/

# 設計フェーズの状態テンプレート
mkdir -p docs/_state
cp "$SRC"/templates/_state_phase_status_template.md docs/_state/phase_status.md
cp "$SRC"/templates/_state_open_questions_template.md docs/_state/open_questions.md
cp "$SRC"/templates/_state_answers_template.md     docs/_state/answers.md

# 実装フェーズの状態テンプレート(実装着手前にコピーしておく)
mkdir -p docs/_impl_state/tickets
cp "$SRC"/templates/_impl_state_progress_template.md         docs/_impl_state/progress.md
cp "$SRC"/templates/_impl_state_spec_gaps_template.md        docs/_impl_state/spec_gaps.md
cp "$SRC"/templates/_impl_state_incidents_template.md        docs/_impl_state/incidents.md
cp "$SRC"/templates/_impl_state_review_findings_template.md  docs/_impl_state/review_findings.md

# Claude Code hooks(実装エージェント用 安全弁)
mkdir -p .claude/hooks
cp "$SRC"/hooks/*.py .claude/hooks/
cp "$SRC"/hooks/settings.example.json .claude/settings.json
# Linux/Mac は settings.json の "python" → "python3" に置換するとよい:
sed -i.bak 's|"command": "python |"command": "python3 |g' .claude/settings.json

# Skills(任意 — 実装エージェントが参照する)
mkdir -p skills
cp -r "$SRC"/skills/security-review     skills/
cp -r "$SRC"/skills/spec-traceability   skills/
```

### Windows PowerShell

```powershell
$src = "<このフォルダの絶対パス>"

# サブエージェント (設計 + 実装)
New-Item -ItemType Directory -Force -Path ".claude\agents" | Out-Null
Copy-Item -Path "$src\agents\*.md" -Destination ".claude\agents\"

# 共通ルール（エージェントが起動時に Read する）
New-Item -ItemType Directory -Force -Path ".claude\references" | Out-Null
Copy-Item -Path "$src\references\*.md" -Destination ".claude\references\"

# 設計フェーズの状態テンプレート
New-Item -ItemType Directory -Force -Path "docs\_state" | Out-Null
Copy-Item "$src\templates\_state_phase_status_template.md"   "docs\_state\phase_status.md"
Copy-Item "$src\templates\_state_open_questions_template.md" "docs\_state\open_questions.md"
Copy-Item "$src\templates\_state_answers_template.md"        "docs\_state\answers.md"

# 実装フェーズの状態テンプレート
New-Item -ItemType Directory -Force -Path "docs\_impl_state\tickets" | Out-Null
Copy-Item "$src\templates\_impl_state_progress_template.md"        "docs\_impl_state\progress.md"
Copy-Item "$src\templates\_impl_state_spec_gaps_template.md"       "docs\_impl_state\spec_gaps.md"
Copy-Item "$src\templates\_impl_state_incidents_template.md"       "docs\_impl_state\incidents.md"
Copy-Item "$src\templates\_impl_state_review_findings_template.md" "docs\_impl_state\review_findings.md"

# Claude Code hooks
New-Item -ItemType Directory -Force -Path ".claude\hooks" | Out-Null
Copy-Item "$src\hooks\*.py" ".claude\hooks\"
Copy-Item "$src\hooks\settings.example.json" ".claude\settings.json"

# Skills
New-Item -ItemType Directory -Force -Path "skills" | Out-Null
Copy-Item -Recurse "$src\skills\security-review"   "skills\"
Copy-Item -Recurse "$src\skills\spec-traceability" "skills\"
```

> ℹ️ hooks のコマンドは Windows なら `python`、Linux/Mac なら `python3` が一般的。`settings.json` の指定を環境に合わせて調整してください。Python 3.10+ が必要です。

---

## 起動: 設計フェーズ

設計対象プロジェクトのルートで Claude Code を起動し、こう伝えます:

```
spec-orchestrator を起動して、新しいシステムの設計を始めて。
```

`spec-orchestrator` が Phase 0 のキックオフ質問をチャットに番号付きで提示し、ユーザーの返信を待ちます（AskUserQuestion ツールは使いません）。番号で答えていけば、Phase 1〜6 が順に進み、最終的に `docs/` 配下が一式埋まります。

---

## 起動: 実装フェーズ

`docs/IMPLEMENTATION_GUIDE.md` を含む `docs/` 一式が揃ったら、実装エージェントチームを起動できます:

```
impl-orchestrator を起動して、docs/ の仕様に従って実装を始めて。
```

最初にチャットに番号付きで以下を質問します:

- どのマイルストーンから着手するか (M1 基盤 / M2 コア機能 / 全部 / 個別機能)
- 最大並列度 (1=直列 / 2-3=控えめ / 4+=積極並列)
- git コミット方針

回答後:

1. `impl-ticket-planner` がチケット計画(`docs/_impl_state/tickets/T-XXX.md`)を生成
2. `impl-backend-engineer` / `impl-frontend-engineer` / `impl-db-engineer` / `impl-batch-engineer` / `impl-test-engineer` が **並列実行** でコードを書く
3. マイルストーン末に `impl-security-reviewer` と `impl-code-reviewer` が走り、`docs/_impl_state/review_findings.md` に指摘集約
4. 必要なら修正チケットを起票して次マイルストーンへ

成果物は **`src/` 配下**(+ ルート直下の設定ファイル + `tests/` + `.github/workflows/`)に出力されます。

---

## 起動: インフラ構築フェーズ

設計 `docs/` 一式（特に `docs/01_requirements/` の非機能要件 NF-XXX と `docs/02_basic_design/` の技術スタック）が揃ったら、AWS インフラ構築エージェントチームを起動できます。実装 `src/` の完成は必須ではありません（あればビルド/配信要件の裏取りに使われます）。

```
infra-orchestrator を起動して、docs/ に従って AWS インフラ構成を固めて。
```

最初にチャットに番号付きで以下を質問します:

- クラウド（既定 AWS）/ 想定トラフィック・ピーク
- 予算上限の有無と水準
- 収束ループの上限 M（既定 3 周）

回答後の流れ:

1. `infra-architect` が `docs/(+src/)` を棚卸しし、AWS 構成ドラフトと承認用 HTML 図解（`docs/06_infrastructure/architecture.md` / `diagram.html`）を生成
2. **IP3 収束ループ**: 「非機能要件 × インフラ構成 × コスト」を突き合わせ、矛盾（予算超過など）があれば **(1)予算を上げる / (2)NFを緩める / (3)構成を簡素化する** の3択を番号付きで確認。`cost-estimator` がインフラ費を再見積りし、3条件が揃うまで反復（`docs/06_infrastructure/reconciliation_log.md` に記録）
3. **★承認ゲート**: `diagram.html` をユーザーが承認し、`spec-critic` が PASS するまで Terraform を書きません
4. 承認後、`terraform-generator` がモジュール分割構成の `terraform/` を生成（各リソースに `@spec IN-XXX <- NF-XXX` コメント付き）
5. `deployment-engineer` が CI/CD パイプライン（`.github/workflows/` 等）と手順書（`docs/06_infrastructure/deployment.md`）を出力（OIDC 鍵レス既定）
6. マイルストーン末に `spec-critic` / `impl-security-reviewer` が fmt/validate・セキュリティ・コスト・整合を検品

成果物は **`terraform/` 配下**（モジュール分割）+ `docs/06_infrastructure/` + CI/CD 定義に出力されます。`terraform apply` / 実デプロイはこのチームでは実行せず、手順書に従ってユーザーが行います。

> ℹ️ 手動配置（方法B）の場合、`references/INFRA_RULES.md` は `cp references/*.md` の手順で自動的に `.claude/references/` にコピーされます。追加作業は不要です。

---

## 個別エージェントを直接起動する場合

特定フェーズ・特定エージェントだけ呼べます。

設計フェーズ:
```
solution-architect で構成方式の比較だけしてほしい。
requirements-analyst で機能要件と非機能要件だけ詰めて。
ui-mock-designer でログイン画面とダッシュボードのモックだけ作って。
cost-estimator で現状の docs/ からコスト概算 PDF を作って。
```

実装フェーズ:
```
impl-ticket-planner で M1 のチケットだけ作って。
impl-security-reviewer で src/ の現状をレビューして。
impl-code-reviewer で M1 の仕様準拠チェックだけして。
```

インフラ構築フェーズ:
```
infra-architect で現状の docs/ から AWS 構成案と図解だけ作って。
terraform-generator で承認済み構成から Terraform だけ生成して。
deployment-engineer で CI/CD パイプラインとデプロイ手順書だけ作って。
```

---

## 進捗の見える化

| ファイル | 何が見える |
|---|---|
| `docs/_state/phase_status.md` | 設計フェーズの進捗 |
| `docs/_state/answers.md` | 設計時の Q&A ログ |
| `docs/_state/open_questions.md` | 設計の未解決事項 |
| `docs/_impl_state/progress.md` | 実装ダッシュボード |
| `docs/_impl_state/tickets/T-XXX.md` | 個別チケット状態 |
| `docs/_impl_state/spec_gaps.md` | 実装中に発見された仕様の欠落 |
| `docs/_impl_state/incidents.md` | ルール違反・失敗ログ |
| `docs/_impl_state/review_findings.md` | レビュー指摘集約 |

---

## hooks の動作確認

```bash
# わざと docs/ に書き込みを試みる(impl-orchestrator 起動中 = .impl_active マーカーがある状態で)
# → docs_readonly_guard.py がブロックすれば OK

# わざと API キーらしき値をコードに書く
# → secret_guard.py がブロックすれば OK
```

- `docs_readonly_guard` は `docs/_impl_state/.impl_active` マーカーがある時（=実装フェーズ中）だけブロックします。設計フェーズに戻る場合はマーカーを削除してください。変更管理フロー（`spec-change-manager`）が `docs/_impl_state/.docs_edit_unlock` を立てている間は docs/ 更新が許可されます（実装変更に伴い docs も併せて更新するための例外）。
- hooks を一時的に切りたい場合（手動配置時）は `.claude/settings.json` から該当 hook を外すか、`.claude/settings.json.disabled` にリネーム。プラグイン利用時はプラグインを無効化してください。

---

## トラブルシュート

- **質問が出てこない**: `spec-orchestrator` を明示的に呼び直してください
- **モックが思った感じと違う**: `ui-mock-designer` に「もう少し業務系/モダン/ミニマルに寄せて」など追加指示
- **設計途中で大きな変更が必要**: 該当の設計書を直接編集 → `docs/_state/answers.md` に変更ログ追記 → 影響を受けるフェーズのエージェントを再起動
- **実装中に仕様の不備に気付いた**: `docs/_impl_state/spec_gaps.md` に書かれているので確認 → 必要なら設計エージェントを呼んで仕様修正
- **設計フェーズなのに docs/ への書き込みがブロックされる**: `docs/_impl_state/.impl_active` マーカーが残っている可能性。削除してください
- **hook が誤検出する**: hook スクリプトの該当パターンを調整（`references/IMPL_RULES.md` のルールはエージェント側でも守られる）
- **並列実行で同じファイルが書き換わる**: チケットの `estimated_files` が重複している可能性。orchestrator にチケット見直しを依頼
