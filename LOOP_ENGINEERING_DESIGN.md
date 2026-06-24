# yoken-teigi-kun ループエンジニアリング導入設計

> 作成日: 2026-06-24 / 対象バージョン: v0.11.0
> 位置づけ: **提案ドキュメント**（retrospective と同じく human-in-the-loop。本書はプラグイン本体を書き換えない。承認後に別セッションで反映する）

---

## 0. 要約（結論先出し）

このプラグインは設計思想としては既に **orchestrator-workers ループ**（spec/impl 両 orchestrator が専門エージェントを委譲）と、**人間ゲート付きメタ改善ループ**（retrospective）を持っている。つまり「ハーネス層」までは完成している。足りないのは、**ハーネスの内側で自律的に回る検証ループ（loop 層）** である。

最新のループエンジニアリングが言う「act → 実環境からフィードバック → 判断 → 終了条件まで繰り返す」のうち、このプラグインに欠けているのは次の3点に集約される。

1. **決定的検証（deterministic verifier）を回す内側ループがない** — DoD は「lint/type/test が green」を要求するが、*green にするまで回すループ*が手順化されていない。
2. **終了条件・無進捗検知・予算ガードが一級市民になっていない** — 「同一チケット3連続失敗でエスカレーション」だけが点在する。
3. **走行中に学ぶ速いループ（Reflexion）がない** — 学びは retrospective の「案件をまたぐ遅いループ」しかなく、同一走行内では同じ失敗を繰り返す。

以下、根拠 → 現状棚卸し → ギャップ → 導入設計（優先度付き）→ 入れない場所 → ロードマップ、の順で示す。

---

## 1. ループエンジニアリングとは（調査要約）

2026年6月、「コーディングエージェントに毎回プロンプトを打つのではなく、エージェントを駆動する**ループそのものを設計する**」という考え方が `loop engineering` という名前で急速に広まった（Peter Steinberger / Addy Osmani）。AI との付き合い方は次の4層で外側に拡張してきた、と整理される。

```
prompt engineering  (2022–24) … 言葉を最適化する
   ⊂ context engineering (2025) … モデルが見る情報を最適化する
      ⊂ harness engineering (2026) … エージェントが動く環境（足場・ツール・制約・状態）を作る
         ⊂ loop engineering (2026) … その環境の中で「目標まで回り続ける周期」を設計する
```

**よく設計されたループの解剖（このプラグインの評価軸に使う）**

| 構成要素 | 内容 |
|---|---|
| 検証可能な終了条件を持つ目標 | 「テストを通す」は良い目標、「コードを良くする」は悪い目標（止まれない） |
| 実環境に触れるツール群 | ファイル・ターミナル・テストランナー・型チェッカ・VCS |
| コンテキスト管理 | 各ステップが次に積み上がるので、要約・剪定・外部化で窓を溢れさせない |
| 終了・エスカレーション論理 | 成功/失敗の明示的な出口 ＋ 詰まったら人間へ |
| 回復可能/致命の区別 | テスト失敗＝行動材料、資格情報欠落＝即停止 |

**主要パターン（適材適所で選ぶ）**

- **ReAct** … reason → act → observe を繰り返す基本形。全ループの祖。
- **Reflexion** … Actor / Evaluator / Self-Reflection の3役。失敗の教訓を言語化してエピソード記憶に書き、次の試行が読み返す。*同一セッション内で*賢くなる。
- **Plan-and-Execute** … 計画役と実行役を分離。長いタスクのドリフトを抑える。
- **Evaluator-Optimizer** … 生成役と評価役を分け、評価が通るまで往復。明確な受け入れ基準があるときに強い。
- **Orchestrator-Workers** … 中央が分解し、各サブエージェントを独立コンテキストで並列実行して統合。

**3つの難所**: コンテキスト管理 / 終了・無進捗検知 / 検証（報酬信号）。特に検証は「決定的検証（テスト・型・lint）を最優先、LLM-as-judge は機械検証できない部分に限定」が鉄則。

**主要な失敗モード**: コンテキスト腐敗、無進捗ループ、目的の誤指定（報酬ハック＝テストを消して CI を緑にする等）、検証なき「完了」誤報、誤差の雪だるま、コスト暴発。

---

## 2. 現状棚卸し：このプラグインに既にあるループ的要素

| 既存要素 | 該当パターン | 評価 |
|---|---|---|
| spec/impl 両 orchestrator が専門エージェントに委譲・並列起動 | Orchestrator-Workers | ◎ 完成度高い。`touches_shared` による直列化・依存グラフ循環検出まである |
| spec-critic が各フェーズ完了時にアンチレビュー → FAIL なら差し戻し | Evaluator-Optimizer の片鱗 | △ 生成役と評価役は分離済み。ただし**往復が有界ループとして定義されていない** |
| retrospective が案件をまたいで弱点を集約し改善提案 | メタ改善ループ（遅い Reflexion 相当） | ◎ 思想は優秀。ただし**案件単位の遅いループのみ** |
| `_state` / `_impl_state` への状態外部化＋再開プロトコル | External state / コンテキスト外部化 | ◎ セッション跨ぎ再開は loop の external-state そのもの |
| hooks（secret/PII/docs-readonly/@spec/format） | ハーネスのガードレール | ◎ harness 層は強い |
| 「同一チケット3連続失敗でエスカレーション」（impl-orchestrator 原則7） | 無進捗検知の萌芽 | △ 1か所だけ。汎用ルール化されていない |
| DoD で lint/type/test green を要求（R-8, M-4） | 決定的検証の*基準* | △ 基準はあるが「green にするまで回すループ手順」がない |

要するに **harness 層は完成、loop 層が点在しているが体系化されていない**。

---

## 3. ギャップ分析（loop 解剖の各軸 × 現状）

| ループの軸 | 設計フェーズ | 実装フェーズ |
|---|---|---|
| 検証可能な終了条件 | critic 判定（LLM-as-judge）あり | DoD あり。ただし**決定的検証を回すループ未定義** ← 最大ギャップ |
| 実環境ツール | 主に対話。検証は人間 | Bash/test あるが「自動で回す」手順が薄い |
| コンテキスト管理 | サブエージェント独立窓は◎ | 長い走行の compact/prune ルールなし |
| 終了・エスカレーション | critic FAIL→差し戻しはあるが**反復上限なし** | 3連続失敗のみ。**予算ガード・無進捗の汎用定義なし** |
| 回復可能/致命の区別 | 暗黙 | 暗黙（spec_gaps=要エスカレーション止まり） |
| 走行内学習（Reflexion） | なし | なし（incidents は記録のみ、読み返さない） |
| 報酬ハック対策 | — | **なし**（テスト削除で緑化を防ぐ仕組みがない） |

---

## 4. 導入設計（優先度順）

### 提案A【最優先】実装フェーズに「決定的検証ループ」を一級市民化する

**狙うギャップ**: 検証可能な終了条件 / 検証＝報酬信号 / 完了誤報の防止。

**現状の問題**: R-8 の DoD は「lint/type/test green」を*完了条件*として要求するが、各 engineer がそれを**どう回して green に到達するか**は手順化されていない。結果、エージェントは「実装した→たぶん通る」で `done` を主張しがち（＝ハルシネーション完了）。これは loop engineering が「決定的検証を毎ステップ入れろ」と最も強く言う点。

**設計**: 各 impl-*-engineer のチケット処理を、明示的な ReAct + 決定的検証ループとして定義する。

```
ticket を claim
loop (最大 N 回, 既定 N=3):
    実装/修正を書く
    決定的検証を実行: lint / type-check / 該当テスト   ← 報酬信号
    全 green か?
        yes → evidence にコマンド出力を貼り status=done で抜ける
        no  → 失敗ログを読む。前回と同じ失敗が続くなら無進捗 → break してエスカレーション
予算超過 or N 回超過 or 無進捗 → orchestrator へエスカレーション（コードを書き続けない）
```

**宛先アーティファクト**:
- `references/IMPL_RULES.md` に新節「R-9: 検証ループ（Definition of Done に到達する手順）」を追加。DoD（R-8）が*状態*の定義なら、R-9 は*そこへ至る周期*の定義。
- 各 `agents/impl-*-engineer.md` の「完了の定義」に「R-9 の検証ループを回し、evidence に最終コマンド出力を貼る」を1行追記。
- `templates/_impl_ticket_template.md` の `## 証拠 (Evidence)` に「検証ループの試行回数・最終 green ログ」欄を追加。

**終了条件**: 全 green（決定的）。**反証可能な期待効果**: 次案件で code-reviewer 指摘のうち「テスト未通過/型エラー残り」カテゴリ件数が減る。

---

### 提案B【高】設計フェーズの critic↔designer を「有界 Evaluator-Optimizer ループ」に明示化

**狙うギャップ**: 終了・反復上限 / 無進捗検知（設計側）。

**現状の問題**: spec-critic は生成役（designer）と評価役が分離された理想的な Evaluator-Optimizer の片割れだが、「FAIL→差し戻し→修正→再レビュー」の**往復に上限がない**。同じ BLOCKER が手を変え品を変え出続けると、収束しないまま反復し得る（あるいは逆に1回で諦めてゲートを飛ばす誘惑が出る）。

**設計**: critic↔designer の往復を有界ループとして spec-orchestrator に定義する。

```
loop (最大 M 回, 既定 M=2):
    designer がフェーズ成果物を生成/修正
    spec-critic がレビュー → PASS / PASS_WITH_CONDITIONS / FAIL
    PASS → 次フェーズ
    PASS_WITH_CONDITIONS → 条件を open_questions に登録して次フェーズ
    FAIL → 差し戻し。ただし:
        同一カテゴリの BLOCKER が2回連続 → 無進捗 → ユーザーへ番号付きエスカレーション
M 回超過 → ユーザー裁定（自動で回し続けない）
```

**宛先アーティファクト**:
- `agents/spec-orchestrator.md` 原則3を拡張（反復上限・無進捗検知・エスカレーションを明文化）。
- `templates/_phase_review_template.md` に「反復回数（iteration）」「前回 FAIL からの差分」欄を追加（retrospective が差し戻し回数を機械集計しやすくなる副次効果）。

**終了条件**: critic PASS（LLM-as-judge）。設計成果物は決定的検証が効きにくいので judge で正しい。ただし**機械検証できる部分（ID 参照・リンク切れ・TODO 残り）は critic が既に Bash 検証している** → これは「決定的検証を judge の前に置く」鉄則に合致しており、現状維持で良い。

---

### 提案C【中】走行内 Reflexion：エピソード教訓バッファ `lessons.md`

**狙うギャップ**: 走行内学習（速いループ）。retrospective（案件をまたぐ遅いループ）との間を埋める。

**現状の問題**: `incidents.md` は失敗を*記録*するが、同一走行中の他エージェントが*読み返して*同じ轍を避ける仕組みがない。retrospective は次案件にしか効かない。Reflexion の核心は「失敗の言語化を即座に次の試行へ渡す」こと。

**設計**:
- `docs/_impl_state/lessons.md`（エピソード記憶）を新設。提案A の検証ループで失敗→回復したエンジニアが「教訓1行＋原因＋回避策」を追記する（例:「T-012: テスト失敗。原因=import パス。回避=schemas は src/schemas から import」）。
- 各 impl-*-engineer は**起動時に lessons.md を Read**（IMPL_RULES の起動手順に追記）。orchestrator が起動プロンプトで明示。
- 案件完了時、retrospective が lessons.md を入力に加える（速いループ→遅いループへ昇格）。

**宛先アーティファクト**: `references/IMPL_RULES.md` §4.2 の状態ディレクトリに `lessons.md` 追加、起動手順に Read 追記。`templates/` に `_impl_state_lessons_template.md` 追加。`agents/retrospective.md` の入力源リストに追加。

**コスト注意**: lessons.md が肥大化するとコンテキストを食う。**上限（例: 直近20件 or 1画面）を設け、超過分は retrospective が IMPL_RULES への恒久ルール昇格 or 破棄を判断**（compact の思想）。

---

### 提案D【中】終了・無進捗・予算ガードを共通ルール化

**狙うギャップ**: 終了論理が「半分の設計」。現状は点在（impl 原則7の3連続のみ）。

**設計**: loop engineering の終了論理を両 orchestrator の共通語彙にする。`references/IMPL_RULES.md`（と SPEC_RULES）に新節を追加。

- **無進捗検知（汎用）**: 直近 K ステップで「状態が変わらない／同一エラーが続く」なら break。提案A・B の個別実装を一般原則として裏打ち。
- **反復上限**: 検証ループ N=3、設計往復 M=2 を既定値として明記（ユーザーが上書き可）。
- **予算ガード**: マイルストーン単位で「並列度・コミット粒度」は既にユーザーに確認している（impl-orchestrator 契約）。ここに「想定試行回数の上限」を追加し、超過は報告。
- **回復可能/致命の区別**: テスト失敗＝行動材料（ループ継続）、シークレット欠落・依存解決不能・仕様矛盾＝即停止（致命）の分類表を追加。

**宛先アーティファクト**: `references/IMPL_RULES.md` 新節「7'. ループ終了とエスカレーションの規律」、`agents/impl-orchestrator.md` 原則7を参照に置換。

---

### 提案E【中】報酬ハック・検証なき完了のガード（hooks 拡張）

**狙うギャップ**: 目的の誤指定（報酬ハック）/ 完了誤報。loop engineering の代表的失敗「テストを消して CI を緑にする」への防御。このプラグインは hooks 基盤が強いので相性が良い。

**設計**:
- 新 hook `verification_guard.py`（PreToolUse: Write/Edit、`tests/` 配下対象）。テストの削除・`skip`/`xfail`/`it.only` の新規付与・アサーション削除を検出して警告/ブロック。
- 既存 `spec_traceability_check.py` の思想（PostToolUse で @spec を強制）と同型で実装でき、保守負荷が低い。
- IMPL_RULES §6 の失敗パターンに「検証を通すためにテストを弱める/消す」を明記。

**宛先アーティファクト**: `hooks/verification_guard.py` 新規、`hooks/hooks.json` の PreToolUse に追加、`hooks/README.md` に表追加、`references/IMPL_RULES.md` §6 追記。

---

## 5. 入れない場所（ループにしないことの設計）

ループエンジニアリング自身が「多くの場合は対話セッションのほうが速くて安全」「目標を検証できないならループにするな」と釘を刺している。これを守る。

- **Phase 0〜5 のユーザー対話（要件・モック合意・コスト承認）はループ化しない**。これは*人間が回す*ループであり、自動化すると「誰にも聞いていない設計」を生む（SPEC_RULES Q-2 の既存思想と一致）。
- **設計成果物の品質を LLM-as-judge だけで自動往復させすぎない**。提案B で上限 M=2 を置くのはこのため。設計は決定的検証が効きにくく、judge は報酬ハック・共謀のリスクがある。最終判断は人間ゲート（既存思想を維持）。
- **retrospective による自己改善は完全自律にしない**。提案A〜E も含め、プラグイン本体への反映は引き続き human-in-the-loop（本書もその原則に従い提案に留める）。

---

## 6. 段階導入ロードマップ

「まず単一の検証ループ、並列 worktree は後」という現場の定石に従い、最小変更から入れる。

| 段階 | 内容 | 変更規模 | 期待効果（測り方） |
|---|---|---|---|
| 1 | 提案A：検証ループを R-9 として明文化＋ engineer/テンプレ追記 | 小（ルール＋数行×6） | code-reviewer の「未通過/型エラー」指摘件数↓ |
| 2 | 提案D：終了・無進捗・予算ガードの共通語彙化 | 小〜中（IMPL_RULES 1節） | incidents の「暴走/堂々巡り」件数↓ |
| 3 | 提案B：critic↔designer の有界ループ明示 | 中（orchestrator＋テンプレ） | phase_reviews の差し戻し回数の発散↓ |
| 4 | 提案E：verification_guard hook | 中（新 hook 1本） | 報酬ハック型インシデント＝0 を維持 |
| 5 | 提案C：lessons.md（走行内 Reflexion） | 中（新テンプレ＋起動手順＋retro 連携） | 同一走行内の重複失敗↓ |

各段階の効果は **retrospective が次案件で答え合わせできる指標に紐づけてある**（このプラグインの既存の収束条件思想を流用）。

---

## 7. 設計判断の根拠（なぜこの形か）

- **harness は既に強いので、足すのは loop だけ**。hooks・state・references・orchestrator-workers は完成済み。重複投資しない。
- **決定的検証を最優先（提案A・E）**、LLM-as-judge は設計フェーズに限定（提案B）。これは loop engineering の「検証＝報酬信号」鉄則そのもの。
- **速い Reflexion（C）と遅い retrospective を二層に**。既存の retrospective を捨てず、その手前に走行内ループを足す。
- **終了論理を半分の設計として扱う（D）**。反復上限・無進捗・予算・致命/回復の区別を一級市民にする。
- **すべて提案に留め、人間ゲートを維持**。プラグインの自己改善哲学（retrospective）と一貫させる。

---

## 参考文献

- [Loop Engineering](https://addyosmani.com/blog/loop-engineering/) — Addy Osmani, 2026（概念の命名と解剖：automations/worktrees/skills/connectors/sub-agents/external state）
- [What Is Loop Engineering? A Complete Guide (2026)](https://tosea.ai/blog/loop-engineering-ai-agents-complete-guide-2026) — Tosea.ai（4層史観・解剖・パターン・失敗モードの整理）
- [Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents) — Anthropic, 2024（Evaluator-Optimizer / Orchestrator-Workers）
- [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — Anthropic, 2025
- [ReAct](https://arxiv.org/abs/2210.03629) — Yao et al., 2022
- [Reflexion](https://arxiv.org/abs/2303.11366) — Shinn et al., 2023
