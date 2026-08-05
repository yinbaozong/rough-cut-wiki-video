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

也可以把 `教程步骤` 换成 `教程文件：E:\某次拍摄\步骤.txt`。Agent 不得强制用户创建 Markdown；有粘贴内容时，应原样保存为任务目录中的 `wiki-source.md`，再运行 `scripts/roughcut.py`。CLI 的 `--wiki` 可以读取 `.txt`、`.md` 或其他 UTF-8 文本文件。`--mode auto` 使用语音、文件名和步骤顺序；`--mode filename` 完全跳过语音并保留文件完整时长。两种模式都不抽帧、不做画面 OCR。

`auto` 的固定顺序是：并行提取全部音轨 → 识别词级时间戳 → 判断口播是否与教程步骤有关 → 无有效口播时检查文件名。语音模型每个进程只加载一次，不抽帧、不做画面 OCR。两者都无法关联教程步骤时不能只靠步骤顺序猜测；保留完整源素材，在时间线末尾标记 `待确认`，并在审核报告说明“无报幕且无有效文件名”。

## 识别参数

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--language` | `zh` | 固定中文。自动检测实测慢约一倍，且会把模糊报幕判成其它语种并返回该语种文本。确认素材不是中文时才传 `--language ""` |
| `--workers` | 6 | 探测与音轨提取的并发数。12 个 4K 文件实测由 93 秒降到 16 秒 |
| `--batch-size` | 2 | 批量推理规模。实测 2 优于 8，两者都优于逐段推理 |
| `--chunk-length` | 10 | 每块秒数。素材多为 10 到 40 秒，30 秒默认值会填充大量空白 |
| `--cpu-threads` | 逻辑核 × 2/3 | 混合架构 CPU 上避开能效核 |
| `--lexicon` | 无 | 术语表，一行一词，用于识别后纠错 |

不要为了提速调低 `beam_size`：贪心解码会把「移除底壳」听成「一处地壳」，省下的时间很有限。

本地 CPU 推理有硬下限：每个文件都要付一次 Whisper 编码器 30 秒窗口的代价，约 20 秒，与音频实际长度基本无关。12 个片段（约 255 秒音频）在 8 核笔记本 CPU 上需要 5 到 8 分钟，多进程并行无效（算力已饱和）。想大幅提速只能换 GPU、换更小模型或改用云端识别。调整教程或人工纠正后请用 `--reuse-takes` 复用识别结果，只重算匹配，通常几秒完成。

## 术语纠错

`--lexicon` 指向的词表在识别完成后做保守替换，不参与解码，因此不会引入幻听，词表可以很大。刻意不走 `hotwords`：faster-whisper 会把 hotwords 截断到 223 token，611 条词库只会保留字典序最前的几条，真正需要的部件名全部丢弃。

替换规则：仅处理长度不小于 3 的片段，相似度阈值 0.75（三字词 0.85），只替换不增删，模型原始文本保留在 `spoken_label_raw`，每一处替换都写进 `review.md` 供人工复核。纠错只能纠到词库里存在的术语，词库没有的说法不会被强行改写。

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

复制目录不等于首页注册。正式项目必须同时具备加密内容、相同项目 ID 的元数据和 `root_meta_info.json` 首页条目。完全退出剪映后再正式注册。详细流程见 [jianying10.md](jianying10.md)。

staging 兼容性验证不必每次都做。加密只会因剪映自身或写库变化而失效，所以用指纹判断：

```powershell
python scripts/roughcut.py fingerprint --drafts "D:\Software\JianyingPro Drafts"
```

指纹包含注册表版本号、实际安装目录、`videoeditor.dll` 的大小与修改时间、写库版本。与上次记录一致就跳过 staging，直接注册；不一致（通常意味着剪映升级）就自动补验一次并更新记录。

安装目录无需手动指定。发现顺序是：显式 `--install-dir` → 草稿根目录同级 → 注册表卸载项（`UninstallString` 指向 `<安装根>\uninst.exe`，`InstallLocation` 常为空）→ `LOCALAPPDATA` 与 Program Files，最后在候选中取版本号最高者。

## 一键脚本（Windows）

`scripts/run-job.ps1` 固定了完整流程：产物落在 `<JobRoot>\<JobName>\output`、可选接入词库、按指纹决定是否 staging、注册前检查剪映是否退出。

```powershell
.\scripts\run-job.ps1 -JobName tray-disassembly `
    -Media 'E:\footage\tray' `
    -JobRoot 'E:\roughcut-jobs' `
    -Lexicon 'E:\glossary.txt' `
    -WikiText '移除底壳固定螺丝，取出底壳，安装底壳预锁紧固定螺丝，全部螺丝安装完成后再最终锁紧。'
```

常用开关：`-ReuseTakes` 复用识别结果只重算匹配；`-NoDraft` 只出分析产物；`-ForceStaging` 强制补验；`-FfmpegBin` 把便携 FFmpeg 注入 PATH。脚本含中文，必须存为 **UTF-8 with BOM**，否则 Windows PowerShell 5.1 会按 GBK 解析并报括号不匹配。
