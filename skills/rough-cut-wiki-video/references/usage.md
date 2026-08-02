# 使用说明

## 日常调用

在 Codex、Claude Code、OpenCode 或 Cursor 中说：

```text
使用 rough-cut-wiki-video。
素材：E:\某次拍摄
教程步骤：
步骤一：小心打开外壳，避免拉扯线缆。
步骤二：按下卡扣并取出旧模块。
步骤三：放入新模块并闭合卡扣。
生成可编辑粗剪，并创建剪映草稿。
```

也可以把 `教程步骤` 换成 `教程文件：E:\某次拍摄\步骤.txt`。Agent 不得强制用户创建 Markdown；有粘贴内容时，应原样保存为任务目录中的 `wiki-source.md`，再运行 `scripts/roughcut.py`。CLI 的 `--wiki` 可以读取 `.txt`、`.md` 或其他 UTF-8 文本文件。`--mode auto` 使用语音、文件名、步骤顺序和可选 OCR；`--mode filename` 完全跳过语音并保留文件完整时长。

`auto` 的固定顺序是：提取音轨 → 识别词级时间戳 → 判断口播是否与教程步骤有关 → 无有效口播时检查文件名。两者都无法关联教程步骤时不能只靠步骤顺序猜测；保留完整源素材，在时间线末尾标记 `待确认`，并在审核报告说明“无报幕且无有效文件名”。

## 首次安装

Windows：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1 -Profile full
```

完整安装只使用多语言 faster-whisper `small`。缺失时运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/download-model.ps1
```

不要用 `tiny` 代替。

## 输出

- `wiki-source.md`：原样保存的教程步骤；
- `wiki-steps.json`：结构化步骤；
- `takes.json`：媒体、入出点和证据；
- `edit-plan.json`：通用编辑决策；
- `review.md`：待确认、缺失步骤和降级原因；
- `wiki-subtitles.srt` / `review-subtitles.srt`：两套可导入字幕；
- `timeline.fcpxml`：Final Cut Pro 交换文件；
- `review-preview.mp4`：720p 审核预览。

通用分析不生成任何容易误认为正式草稿的明文 `jianying-draft/`。剪映项目只通过 `jianying10` 生成。

## 剪映注册

复制目录不等于首页注册。正式项目必须同时具备加密内容、相同项目 ID 的元数据和 `root_meta_info.json` 首页条目。先生成不传 `--user-data` 的 staging；完全退出剪映后再正式注册。详细流程见 [jianying10.md](jianying10.md)。
