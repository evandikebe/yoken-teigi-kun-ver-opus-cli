# improvements/ — 自己改善ループ（メタ改善）の台帳

このフォルダは **yoken-teigi-kun プラグイン自身を、案件をこなすたびに強くする**ための記録置き場です。
`retrospective` エージェントが案件の検品・レビュー記録から生成した改善提案の採否・適用履歴を、ここに時系列で残します。

## ループの全体像

\`\`\`
案件を1つ完走（設計〜実装）
   └─ 残るデータ: phase_reviews / review_findings / spec_gaps / CR / open_questions / incidents
        ↓  retrospective エージェント（提案のみ・プラグインは未変更）
案件直下 retrospective/retro-YYYY-MM-DD.md  ← 評価指標つき改善提案
        ↓  人間が一件ずつ承認/却下
別セッションでプラグイン本体に反映（SPEC_RULES / IMPL_RULES / agents / templates / hooks）
   └─ この improvements/ に採否・適用日・version を記録し commit、version を上げる
        ↓
次案件で指標を答え合わせ → 効いた提案は定着、効かない提案はロールバック
\`\`\`

## なぜ「提案だけ」で人間ゲートを挟むのか

完全自律でプラグインが自分を書き換え続けると、品質ゲートが効かないまま劣化が累積し得ます。
評価指標（カテゴリ別指摘件数・差し戻し回数・トレーサビリティ充足率・spec_gaps/CR 件数）で
**改善を測れる形にし、人間が承認したものだけを反映**することで、ループが収束し説明可能になります。

## 記録の付け方

採否を決めたら、このファイルの「適用履歴」に1行追記します。

### 適用履歴

| 適用日 | version | 提案ID（出典 retro） | 宛先 | 概要 | 採否 | 効果（後日追記） |
|---|---|---|---|---|---|---|
| YYYY-MM-DD | v0.10.0 | （例）P-1 / retro-2026-06-16 | references/SPEC_RULES.md | 認可設計の必須チェック追加 | 採用 | 次案件で認可指摘 4→? |
| 2026-06-24 | v0.12.0 | 提案A / LOOP_ENGINEERING_DESIGN.md | IMPL_RULES R-9 / impl-*-engineer×5 / _impl_ticket_template | 検証ループ（実装→決定的検証→green まで反復・検証なき done 禁止） | 採用 | 次案件で「未通過/型エラー残り」指摘↓ を確認 |
| 2026-06-24 | v0.12.0 | 提案D / LOOP_ENGINEERING_DESIGN.md | IMPL_RULES §4.4 / impl-orchestrator 原則7 | ループ終了・無進捗・予算ガード・回復/致命の区別を共通語彙化 | 採用 | 次案件で「暴走/堂々巡り」インシデント↓ を確認 |
| 2026-06-24 | v0.12.0 | 提案B / LOOP_ENGINEERING_DESIGN.md | spec-orchestrator 原則3 / SPEC_RULES Q-7 / _phase_review_template | critic↔designer を有界 Evaluator-Optimizer（M=2・無進捗検知）に明示 | 採用 | 次案件で差し戻し回数の発散↓ を確認 |
| 2026-06-24 | v0.12.0 | 提案E / LOOP_ENGINEERING_DESIGN.md | hooks/verification_guard.py / hooks.json / settings.example.json / hooks README | 報酬ハック（テスト弱体化）防止 hook を新設 | 採用 | 報酬ハック型インシデント=0 維持を確認 |
| 2026-06-24 | v0.12.0 | 提案C / LOOP_ENGINEERING_DESIGN.md | _impl_state_lessons_template / IMPL_RULES §4.2・起動手順 / retrospective 入力源 | 走行内 Reflexion（lessons.md）で速い学習ループを新設 | 採用 | 次案件で同一走行内の重複失敗↓ を確認 |

> 効かなかった提案はロールバックし、その旨も「効果」列に残す（同じ失敗を繰り返さないため）。
