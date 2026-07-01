# インフラ構築エージェント 共通ルール (INFRA_RULES)

> このファイルは **インフラ構築フェーズの全エージェント**（infra-orchestrator / infra-architect / terraform-generator / deployment-engineer）が共有する不変ルール集です。
> 設計フェーズの SPEC_RULES、実装フェーズの IMPL_RULES に対応する「第3のプログラム＝インフラ構築」の土台です。
> 各エージェント定義の「絶対に守るルール」から参照されます。エージェント固有のルールは各定義ファイル側に書きます。

## 参照方法

- プラグインとして導入している場合: `${CLAUDE_PLUGIN_ROOT}/references/INFRA_RULES.md`
- 手動コピーで導入している場合: `.claude/references/INFRA_RULES.md`

---

## I-1: 位置づけ（設計・実装の下流）

インフラ構築プログラムは、設計プログラム（SPEC）が確定させた `docs/` を唯一の真実として、AWS のインフラ構成を確定し、Terraform とデプロイ手順に落とす。実装プログラム（IMPL）が生成した `src/` があればビルド/配信要件の裏取りに使う。

- **入力の最小条件**: `docs/01_requirements/`（特に非機能要件 NF-XXX）と `docs/02_basic_design/`（技術スタック）が存在すること。無ければ「設計フェーズが未完なので実行できない」と呼び出し元／ユーザーに返す。
- **src/ は任意入力**。実装前でもインフラ計画は作れる（構成・コスト・NF の確定が目的）。実装後なら実際のビルド成果物・起動コマンドで精度が上がる。

## I-2: 承認なしに Terraform を書かない（最重要ゲート）

`infra-architect` が出す構成図（`docs/06_infrastructure/diagram.html`）を **ユーザーが明示承認し、かつ spec-critic の検品が PASS するまで**、`terraform-generator` を起動してはならない。「この構成で Terraform 生成に進んでよいか」を必ず番号付きで確認する。これは SPEC_RULES Q-5「承認ゲートを飛ばさない」のインフラ版。

## I-3: NF×構成×コストの収束（作ってから直さない）

非機能要件・インフラ構成・コストは相互依存する。1回作って終わりにせず、**3点が矛盾しなくなるまで反復（収束ループ）してから**確定させる（infra-orchestrator IP3）。収束の経緯は `docs/06_infrastructure/reconciliation_log.md` に残す。

- 予算超過などの矛盾が出たら、勝手に断定せず **(a)予算を上げる / (b)NFを緩める / (c)構成を簡素化する** の3択をユーザーに提示する。
- 見直しで変わった非機能要件は、既存の NF-XXX を**上書き更新**する（SPEC の変更管理に準じる）。黙って別物にしない。

## I-4: トレーサビリティ（@spec）

インフラ要素には識別子 **IN-XXX** を振り、それが満たす非機能要件（NF-XXX）・外部IF（IF-XXX）を明示する。Terraform のリソースには、由来を示す `@spec` コメントを付ける。

```hcl
# @spec IN-003 <- NF-012(可用性99.9%): multi-AZ RDS
resource "aws_db_instance" "main" { multi_az = true ... }
```

これにより後から「この Multi-AZ 構成はどの要件由来か」を双方向に追える。仕様に無いリソースを勝手に足さない。必要なら infra-architect に差し戻す。

## I-5: 成果物の置き場所

- インフラ設計ドキュメントは `docs/06_infrastructure/` に集約する。
- Terraform コードは `terraform/`（モジュール分割構成）。`src/`（アプリコード）とは別ツリー。
- CI/CD 定義はプラットフォーム規約に従う（GitHub Actions なら `.github/workflows/`）。
- 状態・承認は `docs/_state/phase_status.md` のインフラ節に反映する。

## I-6: セキュリティと鍵レスの既定

- 機密値（パスワード・APIキー・接続文字列）はコードに直書きしない。`variable { sensitive = true }` か Secrets Manager / SSM 参照。**シークレットをリポジトリにコミットしない**（secret_guard hook の対象）。
- クラウド認証は **OIDC による鍵レスを既定**とする。長期アクセスキーを置かない。デプロイ用 IAM ロールは最小権限。
- S3 はデフォルトで暗号化・パブリックアクセスブロック ON。`0.0.0.0/0` を開ける場合はコメントで理由必須。

## I-7: 断定しない・適用しない

- コスト概算は「概算・前提付き・レンジ」で出し、断定しない（cost-estimator の規律を踏襲）。
- ソースや設計から読み取れない事項（想定トラフィック・SLA・予算上限）は推測で埋めず、ユーザーに確認する。推測した箇所は「推測」と明記する。
- `terraform apply` や実デプロイは **このプログラムでは実行しない**。生成・整形・検証準備と手順書までが責務。適用はユーザーが手順書に従って行う。

## I-8: 収束ループの終了規律（有界）

IP3 の収束反復は無限に回さない。**既定 M=3 周**まで。周回しても3条件（予算内・NF充足・構成がNFを満たす）が揃わない場合、回し続けず状況を整理してユーザーへ番号付きエスカレーションする（SPEC_RULES Q-7 / IMPL_RULES §4.4 のインフラ版）。各周回の差分は reconciliation_log.md に残す。
