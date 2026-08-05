# 编辑数据接口 1.0

`WikiStep`：`id`、`order`、`branch`、`wiki_text`、`caption_text`、`keywords`、`notes`。

`TakeEvidence`：`source_file`、`duration`、`in`/`out`（可选）、`has_audio`、`spoken_label`（可选）、`transcript_words`（可选）、`ocr_text`（可选，仅兼容旧数据或 `--corrections` 手动注入；分析过程不再抽帧生成）、`end_reason` 和视频探测信息。没有识别到文字时仍保留一条 `end_reason: no_speech` 的完整素材记录。

启用 `--lexicon` 且发生纠错时追加两个字段：`spoken_label_raw` 保存模型原始输出，`lexicon_repairs` 是替换明细列表，每项含 `found`、`corrected`、`score`。未发生纠错时两个字段都不出现，`spoken_label` 即模型原文。`transcript_words` 始终保留原始词级输出，不做繁简归一化，便于回溯。

`edit-plan.json` 的 `recognition` 记录本次识别设置：`language`、`model`、`workers`、`batch_size`、`chunk_length`、`cpu_threads`、`lexicon_file`、`lexicon_terms`，用于复现结果和排查差异。

`EditSegment`：`source_file`、`source_in`、`source_out`、`display_name`、`wiki_step_id`、`wiki_order`、`part_number`、`confidence`、`captions`、`review_caption`、`matched | ambiguous | unmatched` 状态与 `evidence`。`evidence.selected_source` 记录 `manual | spoken | filename`；`needs_user_input` 表示口播与文件名均无法关联教程步骤；`review_reason` 记录待确认原因。

`edit-plan.json` 顶层 `unmarked_files` 列出没有有效报幕和文件名证据的素材。它们不会阻止导出，也不会改名；完整素材按录制顺序放在时间线末尾并标记 `待确认`。`action_required_files` 暂时保留为兼容字段，内容与 `unmarked_files` 相同。

所有时间单位为秒；剪映草稿内部转换为微秒。路径保存为绝对路径，JSON 使用 UTF-8。
