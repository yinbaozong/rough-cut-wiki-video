# 编辑数据接口 1.0

`WikiStep`：`id`、`order`、`branch`、`wiki_text`、`caption_text`、`keywords`、`notes`。

`TakeEvidence`：`source_file`、`duration`、`in`/`out`（可选）、`has_audio`、`spoken_label`（可选）、`transcript_words`（可选）、`ocr_text`（可选）、`end_reason` 和视频探测信息。没有识别到文字时仍保留一条 `end_reason: no_speech` 的完整素材记录。

`EditSegment`：`source_file`、`source_in`、`source_out`、`display_name`、`wiki_step_id`、`wiki_order`、`part_number`、`confidence`、`captions`、`review_caption`、`matched | ambiguous | unmatched` 状态与 `evidence`。`evidence.selected_source` 记录 `manual | spoken | filename`；`needs_user_input` 表示口播与文件名均无法关联教程步骤；`review_reason` 记录待确认原因。

`edit-plan.json` 顶层 `unmarked_files` 列出没有有效报幕和文件名证据的素材。它们不会阻止导出，也不会改名；完整素材按录制顺序放在时间线末尾并标记 `待确认`。`action_required_files` 暂时保留为兼容字段，内容与 `unmarked_files` 相同。

所有时间单位为秒；剪映草稿内部转换为微秒。路径保存为绝对路径，JSON 使用 UTF-8。
