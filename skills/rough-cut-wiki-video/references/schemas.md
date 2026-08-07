# 编辑数据接口 1.0

`WikiStep`：`id`、`order`、`branch`、`wiki_text`、`caption_text`、`keywords`、`notes`。

`TakeEvidence`：`source_file`、`duration`、`in`/`out`（可选）、`has_audio`、`spoken_label`（可选）、`transcript_words`（可选）、`ocr_text`（可选，仅兼容旧数据或 `--corrections` 手动注入；分析过程不再抽帧生成）、`end_reason` 和视频探测信息。没有识别到文字时仍保留一条 `end_reason: no_speech` 的完整素材记录。

第一层自动纠错发生时追加两个字段：`spoken_label_raw` 保存模型原始输出，`lexicon_repairs` 是替换明细列表，每项含 `found`、`corrected`、`score`。未发生纠错时两个字段都不出现，`spoken_label` 即模型原文。第一层只改写与已知正确术语不重叠、且改动字发音相近的片段；`pypinyin` 缺失时该层整体停用。`transcript_words` 始终保留原始词级输出，不做繁简归一化，便于回溯。

第二层确认生效时再追加两个字段：`spoken_label_before_review` 保存纠错前文本（撤回时据此恢复），`lexicon_accepted` 记录已生效的替换，每项含 `found`、`corrected`。把决策改回 `reject` 后两个字段会被清除。

`lexicon-review.json` 是第二层的往返文件：

- 顶层：`schema_version`、`instructions`、`pinyin_available`、`review_confidence`、`procedure_terms`、`glossary_terms`、`pending`、`accepted_applied`、`proposals`。
- 每条提案：`take`（`文件名#入点` 形式的稳定标识）、`source_file`、`spoken_label`、`source`（`procedure | glossary`）、`found`、`suggested`、`char_score`、`pinyin_score`、`rank`、`preview`（替换后的完整文本）、`current_step`、`current_confidence`、`resulting_step`、`resulting_confidence`、`resulting_step_text`、`decision`（`pending | accept | reject`）、可选 `decision_note`。

`found` 记录的是要被替换的**原文片段**而不是下标，因此不受前序替换导致的位移影响。`resulting_step_text` 给出接受后会落到的步骤原文，是做语义判断的主要依据；不要仅按 `rank` 或 `resulting_confidence` 决策。`source` 为 `procedure` 的提案可信度通常更高：只有教程里出现过的说法才可能匹配到步骤。提案已按来源排序，`procedure` 在前，与其片段重叠的 `glossary` 提案不会出现。

`edit-plan.json` 顶层 `skill_version` 记录生成该工程的 Skill 版本。`recognition` 记录本次识别设置：`language`、`model`、`workers`、`batch_size`、`chunk_length`、`cpu_threads`、`lexicon_file`、`procedure_terms`、`glossary_terms`、`vocabulary_terms`、`pinyin_available`，用于复现结果和排查差异。顶层 `lexicon_review` 汇总本次的 `file`、`pending`、`accepted_applied`。

`EditSegment`：`source_file`、`source_in`、`source_out`、`display_name`、`wiki_step_id`、`wiki_order`、`part_number`、`confidence`、`captions`、`review_caption`、`matched | ambiguous | unmatched` 状态与 `evidence`。`evidence.selected_source` 记录 `manual | spoken | filename`；`needs_user_input` 表示口播与文件名均无法关联教程步骤；`review_reason` 记录待确认原因。

`edit-plan.json` 顶层 `unmarked_files` 列出没有有效报幕和文件名证据的素材。它们不会阻止导出，也不会改名；完整素材按录制顺序放在时间线末尾并标记 `待确认`。`action_required_files` 暂时保留为兼容字段，内容与 `unmarked_files` 相同。

所有时间单位为秒；剪映草稿内部转换为微秒。路径保存为绝对路径，JSON 使用 UTF-8。
