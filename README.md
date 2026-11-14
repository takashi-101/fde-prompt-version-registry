# FDE Prompt Version Registry（プロンプト版管理・回帰判定レジストリ）

[![tests](https://github.com/takashi-101/fde-prompt-version-registry/actions/workflows/tests.yml/badge.svg)](https://github.com/takashi-101/fde-prompt-version-registry/actions/workflows/tests.yml)

プロンプトの本文を、名前と版（バージョン）ごとに評価スコアとともに JSON ファイルへ保存し、2つの版のスコアを比べて回帰（更新後に品質が下がること）が起きていないかを判定する小さなレジストリです。評価スコアは、利用者が別の手段で測って渡します。このツールは評価を実行しません。

## 30秒で読む要点
- **版ごとに本文・スコア・ハッシュを保存します**：`register` は、本文の SHA-256（内容から決まる固定長の値）の先頭12文字を `content_hash` として付け、JSON ファイルに書き出します。同じ名前と版で登録し直すと上書きします。
- **回帰の判定はスコアの比較だけです**：`check_regression(name, base_ver, cand_ver)` は、候補の版のスコアが基準の版以上なら `True`（回帰なし）、下回れば `False` を返します。登録されていない版を指定すると `KeyError` です。
- **標準ライブラリだけで動きます**：外部との通信や有料APIは使いません。テスト24件（正常・境界・異常）を、CI（GitHub Actions による自動テスト）で Python 3.11 と 3.12 で実行しています。

## 見本を動かす
`examples/sample_prompts.json` は、架空の問い合わせ分類プロンプトの3つの版と、比べる組の一覧です。スコアは架空の値で、実際に評価したものではありません。

```
python examples/run_example.py examples/sample_prompts.json
```
```
register inquiry_triage v1 eval_score=0.82 content_hash=0a82aef70f9e
register inquiry_triage v2 eval_score=0.88 content_hash=f7906ec470e4
register inquiry_triage v3 eval_score=0.79 content_hash=2d4eacd1323f
check_regression inquiry_triage v1 -> v2: True
check_regression inquiry_triage v2 -> v3: False
```
v1 → v2 はスコアが上がったため `True`、v2 → v3 は下がったため `False` です。見本のスクリプトは、レジストリのファイルを一時フォルダに作り、終了時に削除します。`checks` に登録していない版があると、`Specified version not found` と表示して終了コード 2 で終わります。

## 関数
| 関数 | 内容 |
|---|---|
| `PromptRegistry(store_path)` | 保存先の親フォルダを作り、ファイルがあれば読み込みます。ファイルは最初の `register` で作ります。 |
| `register(name, version, template, eval_score)` | 版を登録してファイル全体を書き直し、`PromptVersion` を返します。 |
| `get(name, version)` | 登録した版の `PromptVersion` を返します。無ければ `None` です。 |
| `check_regression(name, base_ver, cand_ver)` | 候補のスコアが基準のスコア以上なら `True`、そうでなければ `False` です。どちらかの版が無ければ `KeyError` です。 |

`PromptVersion` は `name`、`version`、`template`、`eval_score`、`content_hash` を持つデータクラスで、値を書き換えられません。保存ファイルは `{名前: {版: {name, version, template, eval_score, content_hash}}}` の形の JSON（UTF-8、日本語はエスケープしない）です。

## テスト（24件）
```
python -m unittest discover -s tests -v
```
- 正常：保存先の親フォルダを作りファイルはまだ作らないこと、登録と `content_hash`、名前と版ごとの保存、別のインスタンスでの読み込み、`get`、スコアが上がる・下がるときの判定、見本の実行結果。
- 境界：空の本文、同じ本文は同じハッシュ・1文字違えば別のハッシュ、同じ版の上書き、範囲外や文字列のスコアも登録できること、無い版の `get`（`None`）、スコアが同じとき・同じ版どうしの判定（`True`）。
- 異常：JSON として読めないファイル・空のファイル（`json.JSONDecodeError`）、親がファイルのパス（`OSError`）、無い版・名前の判定（`KeyError`）、数値でないスコアの比較（`TypeError`）、`PromptVersion` の書き換え、見本のスクリプトに無い版を渡したとき。

## 制約
- `content_hash` は SHA-256 の先頭12文字（48ビット）です。読み込み時に、本文とハッシュが一致するかは確かめません。
- 評価スコアの型や範囲は検査しません。数値でない値を登録すると、`check_regression` で `TypeError` になります。
- 判定は2つの版のスコアの大小だけです。差の許容幅の設定や、評価の実行はありません。
- 同じ名前と版で登録すると、確認なしで上書きします。上書き前の内容は残りません。
- `register` のたびにファイル全体を書き直します。複数のプロセスからの同時の書き込みは考慮していません。
- JSON として読めないファイル（空のファイルを含む）を指定すると、`PromptRegistry(...)` の時点で `json.JSONDecodeError` になります。

## ファイル構成
```
src/prompt_registry/
  registry.py            PromptRegistry と PromptVersion
examples/
  run_example.py         見本の定義を登録し、check_regression の結果を表示
  sample_prompts.json    見本のプロンプトと比べる組（架空）
tests/                   ユニットテスト
.github/workflows/       CI（Python 3.11・3.12）
```

## ライセンス
MIT
