# 编辑数据接口 1.0

`WikiStep`：`id`、`order`、`branch`、`wiki_text`、`caption_text`、`keywords`、`notes`。

`TakeEvidence`：`source_file`、`duration`、`in`/`out`（可选）、`has_audio`、`spoken_label`（可选）、`transcript_words`（可选）、`ocr_text`（可选）、`end_reason` 和视频探测信息。没有识别到文字时仍保留一条 `end_reason: no_speech` 的完整素材记录。

`EditSegment`：`source_file`、`source_in`、`source_out`、`wiki_step_id`、`wiki_order`、`part_number`、`confidence`、`captions`、`review_caption`、`matched | ambiguous | unmatched` 状态与 `evidence`。`evidence.selected_source` 记录 `manual | spoken | filename`，`needs_user_input` 表示口播与文件名均无法关联 Wiki。

`edit-plan.json` 顶层 `action_required_files` 列出必须由用户补录口播或重命名的素材。列表非空时停止正式导出，避免只凭 Wiki 顺序猜测。

所有时间单位为秒；剪映草稿内部转换为微秒。路径保存为绝对路径，JSON 使用 UTF-8。
