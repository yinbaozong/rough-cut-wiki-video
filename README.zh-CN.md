# rough-cut-wiki-video

[English](README.md) | [简体中文](README.zh-CN.md)

[![Check](https://github.com/yinbaozong/rough-cut-wiki-video/actions/workflows/test.yml/badge.svg)](https://github.com/yinbaozong/rough-cut-wiki-video/actions/workflows/test.yml)

`rough-cut-wiki-video` 是一个可分享、平台无关的 Agent Skill。它会读取 MP4/MOV 素材文件夹和一份按顺序编写的教程步骤，把素材整理成可继续编辑的教学视频粗剪。它适用于安装维修、手工制作、烹饪、产品演示、工作流程、培训、开箱及其他按步骤讲解的视频，不局限于 3D 打印领域。

Skill 会综合分析录制口令、简短步骤口播、文件名、教程步骤顺序和素材时间。默认固定中文简体识别。术语纠错在识别后分两层进行：一层保守自动应用，另一层带拼音比对、只提出同音错字的修复建议交由确认，不自动改写；不抽帧、不做画面 OCR。它不会修改原始 4K 文件，可以输出通用剪辑计划、可编辑字幕、SRT、FCPXML、审核预览，以及 Windows 剪映 10/11 能直接显示并编辑的原生加密草稿。

当前 Skill 版本：**0.3.0**。运行 `python scripts/roughcut.py --version` 可随时确认本机实际版本；每次任务也会把版本写进终端输出、`edit-plan.json` 和 `review.md`，方便日后追溯。

## 目录

- [可以生成什么](#可以生成什么)
- [支持平台](#支持平台)
- [安装](#安装)
- [快速使用](#快速使用)
- [一条命令跑完整任务](#一条命令跑完整任务)
- [工作原理](#工作原理)
- [仓库结构与算法原理](#仓库结构与算法原理)
- [录制视频时应该怎么说](#录制视频时应该怎么说)
- [教程步骤应该怎么提供](#教程步骤应该怎么提供)
- [可选输入：词库与人工修正](#可选输入词库与人工修正)
- [两层术语纠错](#两层术语纠错)
- [素材匹配与排序规则](#素材匹配与排序规则)
- [剪映 10/11 可编辑草稿](#剪映-1011-可编辑草稿)
- [Final Cut Pro 使用方法](#final-cut-pro-使用方法)
- [语音识别模型](#语音识别模型)
- [命令说明](#命令说明)
- [输出文件说明](#输出文件说明)
- [常见问题](#常见问题)
- [隐私、安全和限制](#隐私安全和限制)
- [许可证](#许可证)

## 可以生成什么

- 识别并删除 `三二一开始`、`321开始`、`321走`、单独一句 `开始` 等开拍口令。
- 识别并删除单独一句 `OK`、`过`、`可以`、`好了`、`结束` 等结束口令。
- 不会把 `开始拆卸`、`可以安装` 这类正常句子误判为口令。
- 一个视频文件中录了多组开始/结束口令时，可拆成多个 take。
- 同一个文件切换相邻步骤时，可根据 `下一步，移除支架` 进行粗分段。
- 能把 `安装侧板`、`移除支架` 等简短标签匹配到教程的详细步骤。
- 按教程步骤、明确分段编号和录制时间排序。
- 同一步的重复素材全部保留，不会静默挑选或丢弃。
- 正式字幕以用户提供的教程步骤为事实来源，不直接照抄随口说的内容。
- 生成独立的 `文档字幕` 和 `待确认` 两条文字轨。
- 未匹配素材放到时间轴末尾；未拍摄步骤写入审核报告。
- 保留现场原声，时间线引用原始 MP4/MOV。

## 支持平台

| 平台 | 素材分析 | SRT | FCPXML | 审核预览 | 剪映原生草稿 |
| --- | --- | --- | --- | --- | --- |
| Windows | 支持 | 支持 | 支持 | 支持 | 支持剪映 10/11 |
| macOS | 支持 | 支持 | 支持 | 支持 | 实验能力，建议用 FCPXML 进入 Final Cut Pro |
| Linux | 支持 | 支持 | 支持 | 支持 | 不承诺桌面剪映集成 |

Skill 可由 Codex、Claude Code、OpenCode 和 Cursor 读取。脚本不依赖某个平台的专属目录。

## 安装

### 第一步：安装到 Agent

跨平台安装器需要 Node.js 18 或更高版本。

```powershell
npx skills add https://github.com/yinbaozong/rough-cut-wiki-video `
  --skill rough-cut-wiki-video `
  --agent codex claude-code opencode cursor `
  --global --copy --yes
```

共享安装位置通常是：

```text
~/.agents/skills/rough-cut-wiki-video
```

安装器也可能创建对应平台的兼容目录。

### 第二步：安装运行依赖

Windows 完整安装：

```powershell
cd "$HOME\.agents\skills\rough-cut-wiki-video"
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1 -Profile full
```

macOS/Linux 完整安装：

```bash
cd ~/.agents/skills/rough-cut-wiki-video
chmod +x scripts/setup.sh scripts/download-model.sh
./scripts/setup.sh full
```

`full` 会安装：

- `faster-whisper`：本地多语言语音识别；
- 多语言 `small` 模型；
- ONNX Runtime：语音识别运行时依赖；
- `pypinyin`：术语纠错的拼音比对，纯 Python 无编译依赖；
- 固定提交版本的高版本 `pyJianYingDraft`：用于剪映加密和首页注册；
- FFmpeg/ffprobe 检测。Windows 缺少 FFmpeg 时会显示 `winget` 安装命令。

画面抽帧 OCR 已移除：它显著拖慢分析，却几乎不改变匹配决策。

只有在明确不需要语音识别、只想按文件名处理时，才选择 `core`：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1 -Profile core
```

### 第三步：检查环境

```powershell
.\.venv\Scripts\python.exe .\scripts\roughcut.py doctor --json
```

正常结果应该显示：找到 `ffmpeg`/`ffprobe`，`faster_whisper` 可导入，`small` 模型存在，`pyJianYingDraft` 可导入，`frame_ocr: disabled`，`pinyin_repair: True`。

确认实际安装版本：

```powershell
.\.venv\Scripts\python.exe .\scripts\roughcut.py --version
```

### 第四步：首次运行清单

每台机器只需要做一次，按顺序来：

1. 安装 Skill，并执行上面的 `full` 完整安装。
2. 让 FFmpeg 可用。可以 `winget install --id Gyan.FFmpeg -e`，也可以解压一份便携版放在任意目录，然后给任务脚本传 `-FfmpegBin`，这样不用永久修改系统 PATH。
3. 确认 `doctor` 报告 `small` 模型存在。缺失就运行 `scripts/download-model.ps1`。
4. 仅 Windows、且需要剪映原生草稿时：正常安装剪映 10.x 或 11.x，并至少启动一次，让它生成 `%LOCALAPPDATA%\JianyingPro\User Data` 和草稿目录。记下草稿目录位置，通常是 `D:\Software\JianyingPro Drafts`。
5. 先带 `-NoDraft` 跑一次任务，读 `review.md`。确认识别和匹配没问题后再动剪映。
6. 再去掉 `-NoDraft` 跑同一个任务。第一次生成草稿会触发一次 staging 校验，因为还没有记录过指纹；之后除非剪映或写库变化，都会跳过。

整个过程不涉及剪映账号、授权码或联网激活。这里说的「注册」只是把一条记录写进剪映本机的首页索引，具体写了什么见 [剪映 10/11 可编辑草稿](#剪映-1011-可编辑草稿)。

## 快速使用

最简单的方法是直接对 Agent 说：

```text
使用 rough-cut-wiki-video。
素材：E:\教程素材
教程步骤：
步骤一：小心打开外壳，避免拉扯线缆。
步骤二：按下卡扣，垂直取出旧模块。
步骤三：对准位置轻轻放入新模块，然后闭合卡扣。
生成可编辑粗剪，并创建剪映草稿。
```

可以像上面这样直接把步骤粘贴到对话框，也可以提供本地纯文本或 Markdown 文件：

```text
使用 rough-cut-wiki-video。
素材：E:\教程素材
教程文件：E:\教程素材\步骤.txt
生成可编辑粗剪，并创建剪映草稿。
```

也可以直接运行：

```powershell
$Skill = "$HOME\.agents\skills\rough-cut-wiki-video"
& "$Skill\.venv\Scripts\python.exe" "$Skill\scripts\roughcut.py" run `
  --media "E:\本次拍摄\素材" `
  --wiki "E:\教程素材\步骤.txt" `
  --output "E:\本次拍摄\粗剪输出" `
  --mode auto `
  --preview
```

直接粘贴步骤时，Agent 会先把原文原样保存为任务目录中的 UTF-8 `wiki-source.md`，再运行处理命令。直接使用命令行时，`--wiki` 接受 `.txt`、`.md` 或其他 UTF-8 文本导出文件，不需要抓取网页。

## 一条命令跑完整任务

`scripts/run-job.ps1` 把分析、staging 校验、草稿注册串成一条命令，重复拍摄的项目不用再敲三条命令。仅支持 Windows，并且这个文件必须保存为**带 BOM 的 UTF-8**，否则 Windows PowerShell 5.1 会把里面的中文字符串解析错。

```powershell
& "$Skill\scripts\run-job.ps1" -JobName 托盘拆装 `
  -Media '\\192.168.1.10\素材\托盘拆装' `
  -WikiText '移除底壳固定螺丝，取出底壳，安装底壳预锁紧固定螺丝，全部螺丝安装完成后再最终锁紧。' `
  -JobRoot 'D:\粗剪\jobs' `
  -Lexicon 'D:\粗剪\词库.txt' `
  -FfmpegBin 'D:\粗剪\tools\ffmpeg\bin'
```

它按这个顺序做事：

1. 建立 `<JobRoot>\<JobName>\` 和其中的 `output\`，并只对当前进程把 `-FfmpegBin` 加到 `PATH` 前面。
2. 准备教程步骤。传 `-WikiFile` 就复制成 `wiki.md`；传 `-WikiText` 会按中英文逗号、分号、句号切成编号列表，并把未改动的原文作为注释保留在开头。两个都不传时，复用任务目录里已有的 `wiki.md`。
3. 调用 `roughcut.py run`，带上识别调优参数；`--lexicon` 和 `--corrections` 只在对应文件存在时才加。结束后打印分析耗时。
4. 如果传了 `-NoDraft` 就停在这里，方便先看 `review.md` 再决定要不要生成草稿。
5. 如果有待确认的术语纠错提案，停在这里并提示先判断——此时时间线还可能变化，先做草稿只会白做。`-SkipLexiconReview` 可跳过。
6. 把当前剪映指纹和 `<JobRoot>\.roughcut-state\jianying-fingerprint.json` 比对。不一致（或使用 `-ForceStaging`）时，在任务目录里生成一个临时 staging 草稿，成功后立即删除并记录新指纹。staging 失败会直接中止，不会碰首页索引。
7. 检测到 `JianyingPro.exe` 还在运行就拒绝继续；否则注册正式草稿，名字默认是 `<JobName>-roughcut`，可用 `-DraftName` 覆盖。

| 参数 | 默认值 | 作用 |
| --- | --- | --- |
| `-JobName` | 必填 | 任务目录名，同时作为默认草稿名 |
| `-Media` | 必填 | 素材目录，支持 UNC 网络路径 |
| `-WikiText` / `-WikiFile` | 二选一 | 教程步骤，粘贴文本或本地文件 |
| `-JobRoot` | `.\jobs` | 任务目录和指纹状态的存放位置 |
| `-Lexicon` | 无 | 识别后纠错用的术语表 |
| `-Drafts` | `D:\Software\JianyingPro Drafts` | 剪映草稿根目录 |
| `-UserData` | `%LOCALAPPDATA%\JianyingPro\User Data` | 首页索引所在位置 |
| `-FfmpegBin` | 无 | 临时把便携版 FFmpeg 加入 `PATH` |
| `-Workers` | `6` | 并行探测和提音轨的线程数 |
| `-BatchSize` / `-ChunkLength` / `-CpuThreads` | `2` / `10` / 自动 | 识别吞吐调优 |
| `-ReuseTakes` | 关 | 复用 `takes.json`，完全跳过语音识别 |
| `-NoDraft` | 关 | 只做分析，不生成草稿 |
| `-ForceStaging` | 关 | 指纹一致也强制校验一次 |
| `-SkipLexiconReview` | 关 | 有待确认纠错也直接生成草稿 |

改完 `wiki.md` 或 `corrections.json` 后重跑，加 `-ReuseTakes` 会很快：慢的一直是语音识别，匹配和导出只要几秒。

## 工作原理

自动粗剪严格按照证据处理，不会只凭教程步骤顺序猜素材：

1. **读取教程步骤：** 接受对话框中直接粘贴的内容，或读取 UTF-8 纯文本/Markdown 文件，提取按顺序拍摄的动作、名称、数量、方向和对应步骤的注意事项。
2. **探测所有素材：** 使用 ffprobe 读取时长、音轨、分辨率和流信息。发现的每一个 MP4/MOV 都必须进入剪辑计划或明确的处理报告。
3. **并行分离音轨：** `auto` 模式下，FFmpeg 并发生成临时单声道 16 kHz WAV。原始视频不会被改写。默认固定中文简体识别，可选词库做识别后纠错；不抽帧 OCR。
4. **本地语音识别：** faster-whisper `small` 生成多语言词级时间戳。开始/结束口令决定源素材切割点，开始口令后的短标签作为步骤口播。
5. **判断口播是否与教程有关：** 把口播与每个教程步骤比较。没有文字、只有无效语气词或与步骤完全不相关的内容，不能作为匹配证据。匹配偏弱的素材会生成带拼音比对的纠错提案交给人工/AI 确认，而不是静默改写。
6. **必要时再检查文件名：** 没有有效口播时，从文件名提取动作、对象、顺序号和分段编号，再与教程步骤匹配。
7. **无标记素材保留待确认：** 口播和文件名都无法关联教程步骤时，不猜测步骤，也不修改原始文件名。完整素材放在时间线末尾，编辑计划/FCPXML 的片段显示名设为 `待确认（无报幕且无有效文件名）— 原文件名`；剪映等输出通过独立的 `待确认` 文字轨提示，并在 `review.md` 说明原因。
8. **构建时间线：** 生成源素材入点/出点，按教程步骤和分段编号排序，保留重复 take，冲突素材加入 `待确认`。
9. **生成字幕和通用输出：** 写出教程字幕、SRT、FCPXML、JSON 检查点和可选审核预览。
10. **生成剪辑软件项目：** Final Cut Pro 使用 FCPXML；Windows 剪映单独进行加密草稿生成和首页注册。

这个顺序可以避免最危险的错误：素材完全没有标签，却因为录制时间靠近某个教程步骤而被静默排到错误位置。

## 仓库结构与算法原理

```text
skills/rough-cut-wiki-video/
├── SKILL.md
├── agents/openai.yaml
├── assets/*.schema.json
├── assets/models/faster-whisper-small/   （下载得到，不入 Git）
├── references/*.md
└── scripts/
    ├── roughcut.py
    ├── run-job.ps1
    ├── setup.ps1 / setup.sh
    ├── download-model.ps1 / .sh
    └── roughcut/
        ├── core.py
        ├── media.py
        ├── lexicon.py
        ├── exporters.py
        ├── pipeline.py
        └── jianying10.py
```

### Skill 定义与文档

| 文件 | 作用 |
| --- | --- |
| `SKILL.md` | Agent 唯一会读的入口文件，决定什么时候用、怎么用这个 Skill。包含触发描述、必须遵守的工作流和不能违反的规则。 |
| `agents/openai.yaml` | 给需要清单文件的安装器提供的元数据。 |
| `assets/*.schema.json` | 教程步骤、素材证据、剪辑片段的 JSON Schema。用于校验输出或自己写下游程序。 |
| `references/*.md` | 按需加载的详细文档：`usage.md` 全部参数、`schemas.md` 字段级输出结构、`jianying10.md` 草稿内部机制，以及 `filename-guide.md`、`shooting-guide.md`、`speech-recognition.md`。 |

### 脚本

`roughcut.py` 是命令行入口，三个子命令：`doctor` 报告环境能力，`run` 执行分析和导出，`fingerprint` 打印剪映与写库的指纹。它只负责解析参数并转发。

`pipeline.py` 编排一次 `run`：读教程步骤 → 批量分析素材 → 应用人工修正 → 构建剪辑计划 → 写出全部产物。想知道到底会生成什么、按什么顺序生成，看这个文件。

`media.py` 负责所有接触素材和语音模型的工作。

- 扫描目录识别 `.mp4`、`.mov`、`.m4v`、`.avi`、`.mkv`。
- 用 `ffprobe` 读时长、是否有音轨和流信息。个别文件探测失败时回退到占位元数据并记录警告，不会让整批任务中断。
- 提音轨用线程池并发调用 FFmpeg，输出临时单声道 16 kHz WAV。这一步纯粹是 I/O 等待，并行收益很大：16 个文件的批次从约 93 秒降到 16 秒。
- 识别时模型通过 `lru_cache` 只加载一次，并包进 faster-whisper 的 `BatchedInferencePipeline`。语言固定 `zh`，开启 VAD 过滤，请求词级时间戳。`beam_size` 特意保持库默认值：改成贪心解码会把 `移除底壳` 听成 `一处地壳`，省下的时间却几乎可以忽略。
- 识别始终是主要耗时。在 CPU 上它接近「每个文件一份固定开销」，所以总时间更取决于文件数量，而不是总时长。

`core.py` 只做文本逻辑，不碰 I/O。

- 任何比较之前，先用一张 265 条的转换表把繁体折叠成简体。因为 Whisper 会随机输出 `裝`/`殼`/`絲`，而教程原文是简体。
- 分段逻辑扫描词级时间戳，找开始口令（`三二一开始`、`321走`、单独的 `开始`）和单独成句的结束口令（`OK`、`过`、`可以`、`好了`、`结束`）。匹配锚定整句，所以 `开始拆卸`、`可以安装` 不会被误判成口令。开始口令后紧跟的短句作为步骤口播标签。
- 文件名解析提取顺序号、动作标签和分段编号，并把 `DJI_0001`、`C0001` 这类相机默认名判定为无意义。
- 匹配用字符二元组加上单个动作字符（去掉少量停用字）做评分，公式是 `重合数 / min(两侧词数)`，阈值 `0.34`。达标的步骤再按**绝对共享词数**优先于分数排序——正是这一点避免了 `安装底壳` 这种短步骤抢走本属于 `安装底壳固定螺丝并预锁紧` 的素材：只比分数的话，短步骤会因为「完全被包含」而拿到满分。

`lexicon.py` 在识别之后做术语纠错，分两层，详见 [两层术语纠错](#两层术语纠错)。第一层比字形，并用锚点闸和发音闸把关后自动应用；第二层加入拼音比对提高召回，只提建议不自动应用。之所以放在解码之后：Whisper 的 `hotwords` 会在 223 token 处静默截断，真正的词库根本传不进去；而识别后纠错没有容量上限，代价是毫秒级。

`exporters.py` 写出 `wiki-subtitles.srt`、`review-subtitles.srt`、`timeline.fcpxml` 和可选的 720p 预览。FCPXML 按路径引用原始素材，并把 `文档字幕` 和 `待确认` 作为两条独立标题轨。

`jianying10.py` 生成原生草稿。它从注册表卸载项发现安装位置，`InstallLocation` 为空时回退到解析 `UninstallString`；如果自动更新删掉了你指定的版本目录，会自动挑选最新的有效版本。`fingerprint()` 把注册表版本、安装路径、`videoeditor.dll` 的大小与修改时间、写库版本合成指纹，这就是 staging 校验的判断依据。生成草稿时会写入真实时间线，让 `draft_content.json` 和 `draft_meta_info.json` 的项目 ID 保持一致，调本机 DLL 加密，备份 `root_meta_info.json`，最后写入首页条目。

### 为什么要用本机的 DLL

剪映 10/11 的草稿已经不是明文 JSON，`draft_content.json` 是加密的。你安装目录里的 `videoeditor.dll` 是一个带签名的 63 MB Windows 二进制文件，其中导出了加密/解密函数。写库用 `ctypes.WinDLL` 加载它，构造 MSVC `std::string` 结构体，默认在隔离子进程里调用这些导出函数。整个过程没有逆向、没有重新实现算法，也没有内置任何密钥——用的就是你自己安装的那份代码。这也解释了为什么草稿总能匹配你当前的剪映版本，以及为什么版本一变就值得重新校验一次。

### 安装与辅助脚本

`setup.ps1` / `setup.sh` 创建 `.venv` 并安装依赖。`full` 会装 faster-whisper、ONNX Runtime、固定版本的 `pyJianYingDraft` 和 `small` 模型；`core` 只提供按文件名处理、不做语音识别。`download-model.ps1` / `.sh` 单独下载并校验模型，因为它约 486 MB 且包含超过 GitHub 单文件限制的文件。`run-job.ps1` 就是上面那个端到端封装。

### 不在 Git 里的内容

`assets/models/faster-whisper-small/` 和 `.venv/` 由安装脚本生成。任务目录、`.roughcut-state/`、`.roughcut-backups/` 属于运行数据，应该放在仓库之外。

## 录制视频时应该怎么说

### 推荐开拍格式

动作开始前只说一条短句：

```text
三二一开始，安装侧板，第1段
```

然后直接做动作。完成后停顿约半秒，单独说：

```text
OK
```

同一步继续录制：

```text
三二一开始，安装侧板，第2段
```

如果完成动作后直接停止录像，没有结束口令也可以，文件末尾会被当作正常结束。

### 一个文件里切换步骤

如果同一个长视频包含两个相邻动作，在下一个动作开始前说：

```text
下一步，移除支架
```

边界不够清楚时，Skill 会保留素材并标记 `待确认`，不会静默删除。

### 需要说多少内容

只需要说教程步骤层级的大概动作名和可选分段编号：

- `安装背板，第1段`
- `搅拌面糊`
- `折叠纸张，第2段`
- `包装产品`

不需要讲清楚每一个手部动作，也不需要现场组织完整解说。最终教学字幕会根据用户提供的步骤补全和润色。

### 尽量避免这些内容

- 开始口令之后，不要先闲聊再说步骤名。
- 一条标签里不要同时说几个可能的步骤名称。
- 不要把结束词作为单独一句插在动作中间。
- 如果说错零件名，不要长时间自我纠正；直接停掉重新录一条更容易识别。
- 不要依赖 `DJI_0001`、`C0001`、纯时间戳等相机默认文件名表达步骤。

### 不说话时的文件名方案

如果不想录口令，可以把文件命名为：

```text
010_准备面糊_01.mov
010_准备面糊_02.mov
020_倒入模具_01.mp4
```

文件名不用照抄教程原文，简短但能理解即可。Agent 会根据步骤语义寻找最接近的内容。同一步的明确编号优先于录制时间。

## 教程步骤应该怎么提供

教程步骤可以直接粘贴，也可以来自本地文件。它是字幕的事实来源；口播和文件名主要用来判断素材属于哪一步。

### 推荐结构

```text
步骤一：移除固定螺丝，然后小心取下外壳，避免拉扯线缆。
步骤二：打开卡扣，垂直取出旧模块。
步骤三：对准位置轻轻放入新模块，然后闭合卡扣。
步骤四：装回并锁紧固定螺丝。
```

也可以使用普通编号 `1.`、`2.`、`3.`。不要求 Markdown 标题或复杂格式。

### 编写注意事项

- 只写实际拍摄、需要出现在时间线里的动作。
- 按最终观看顺序写成“步骤一、步骤二、步骤三……”或有序编号。
- 一个编号步骤以一个主要动作目标为主；紧密相关的连续动作可以写在同一步。
- 把名称、数量、方向和注意事项写进对应步骤，例如“小心取下外壳，避免拉扯线缆”。
- 没有拍摄的工具清单、准备工作、背景介绍、开场说明和原理知识都不用写，它们不会参与剪辑。
- 如果存在不同操作分支，只提供本次素材实际拍摄的分支；若多个分支都拍了，则分别标清楚。
- 能写出部件名时，不要只写“安装这个”“拆下它”。
- 不要加入没有依据的营销结论或安全结论。
- 可以直接粘贴普通文字，也可以提供 UTF-8 `.txt`、`.md` 或从 Wiki 导出的文本文件；支持中文文件名和中文路径。

Agent 可以调整语序、补充主语和连接词，让字幕更适合朗读，但不能增加教程步骤里没有提供的对象、食材、零件、数量、数值、方向或安全结论。

## 可选输入：词库与人工修正

这两个文件都是可选的、需要手写的，流程本身不会自动生成它们。正常跑一次任务并不需要它们。

### 词库（`--lexicon`）

UTF-8 纯文本，一行一个词。可以跨任务长期复用，值得长期维护。

```text
热端风扇
底壳固定螺丝
挤出机组件
```

词库需要用户自己准备和提供，脚本不会替用户生成。**没有词库完全可以正常运行**，这不是错误也不是降级：纠错的主要词汇来自教程步骤原文，词库只是补充，用于原文里简写或压根没出现的说法。

少于三个字的词、以及不含中文的行会被忽略——太短的模糊命中往往是巧合而不是真的纠错。词库大不用担心：开销随词条数线性增长，仍在毫秒级。

**为什么步骤原文才是主要来源。** 报幕念的通常就是教程原文，所以原文自带的说法才是真正管用的词汇。真实素材可以直接量出差距：被听成「抵扣布丁螺丝」的报幕，只有步骤原文的「底壳固定螺丝」能还原（拼音 0.839）；而 530 条词库给出的是发音更像、教程里却根本不存在的「进气口」（拼音 0.875）——分数更高，但它匹配不到任何步骤，纯属噪音。因此第二层按来源排序，步骤原文在前，与其重叠的词库提案直接丢弃，同一条素材的候选数由 6 降到 2。

换句话说，**词库越大不等于越准**：它同时也在引入噪音。词库真正的用处是补上原文没写全的专业名词，而不是替代原文。

### 人工修正（`--corrections`）

按源文件名索引的 JSON，作为最高优先级证据，用于个别素材的识别实在救不回来的情况。它是**按任务一次性使用**的：那批素材剪完，这个文件就没有价值了，不要带到下一个任务里。

```json
{
  "C9451.MP4": {
    "manual_step_id": "step-005",
    "manual_label": "再次锁紧底壳固定螺丝"
  }
}
```

`manual_step_id` 直接把素材钉到某一步；`manual_label` 提供一个替代标签，仍然走正常评分。`run-job.ps1` 会自动识别任务目录里的 `corrections.json`。

只有在更省事的办法都不行时才用它：重录一条更短的报幕、把文件改成有意义的动作名、或者把听错的词加进词库。一条修正只修一个任务里的一个素材；一条词库条目则永久修好这个词在所有任务里的识别。

## 两层术语纠错

中文报幕识别错误绝大多数是**同音字**，这一点决定了整个设计。

### 为什么只比字形不够

字形相似度对同音错字完全无效——真实素材里的错误，字面重合是 0：

| 片段 → 术语 | 字形相似度 | 拼音相似度 | 实际 |
| --- | --- | --- | --- |
| 抵扣布丁 → 底壳固定 | 0.00 | 0.76 | 应该改 |
| 顶核 → 底壳 | 0.00 | 0.60 | 应该改 |
| 半动 → 安装 | 0.00 | 0.53 | 应该改 |
| 热端风扇 → 冷端风扇 | 0.75 | 0.87 | 绝不能改 |
| 紧抵扣 → 进气口 | 0.00 | 0.88 | 绝不能改 |

### 为什么只比拼音也不够

看最后两行：语义完全相反的 `热端风扇/冷端风扇` 拼音相似度 0.87，比正确修复 `抵扣布丁→底壳固定` 的 0.76 还高。**不存在能把两者分开的阈值。** 只按分数自动应用，迟早会把「热端」改成「冷端」，字幕含义直接反掉。

所以拼音层擅长的是**发现**，不是**判决**。

### 两层怎么分工

**第一层（Python，自动）** 只应用字形已经很接近的替换（阈值 0.75，三字词 0.85），并额外加两道安全闸。自动层无人复核，误改远比漏改危险，所以：

1. **锚点闸**：不改写与「文本里已经写对的已知术语」重叠的片段。词汇表自身的近邻足以越过任何字形阈值，因此被改写风险最高的恰恰是本来就正确的文本。
2. **发音闸**：只比较**发生变化的那几个字**，要求发音相近（阈值 0.7）。Whisper 的错都是音近错；音不近，就不是听错，而是另一个词。

两道闸都由真实数据定标。用户那份 530 条词库中有 **77 对**只差一两个字的合法术语，加闸前实测：

| 输入（本身已经正确） | 加闸前被自动改成 | 加闸后 |
| --- | --- | --- |
| 更换冷端风扇 | 更换**热**端风扇（语义相反） | 不变 |
| 检查热端风扇 | **检主**热端风扇（把对的改错） | 不变 |
| 安装底壳固定螺丝 | **移除**底壳固定螺丝（动词翻转，进错步骤） | 不变 |
| 安装热端风山 | 安装热端风**扇**（这条是正确修复） | 仍然修复 |

发音闸在 0.7 上把 77 对合法近邻**全部**拦下，同时保留所有真实听错——真实听错基本都是完全同音替换（山/扇、私/丝、克/壳），余量充足。`冷/热` 是 leng/re，`山/扇` 同为 shan；字形上两者都是「4 字差 1 字、相似度 0.75」，只有发音能分开。`pypinyin` 缺失时第一层整体停用，而不是无闸运行。

**第二层（AI 确认，不自动应用）** 加入拼音比对来提高召回，结果写进 `lexicon-review.json` 等待判断。判断者拥有分数没有的东西：步骤原文和语义。它一眼就能看出步骤里写的是「底壳固定螺丝」而从来没提过「底座锁定螺丝」，也能看出报幕说的是「再次锁紧」，不可能是「移除」。这一层刻意保持宽松、不套用上面两道闸：错的提案可以否掉，从未出现的提案却找不回来。

只有匹配置信度低于 `--review-confidence`（默认 0.70）的素材才会生成提案——已经高置信度匹配的素材没有可改的余地。同时会丢掉「改了也落在同一步」的提案，因为那不影响成片。

### 实际效果

真实素材 C9451 的报幕被听成 `再次锁紧抵扣布丁螺丝1`，原本匹配不到任何步骤、只能落到时间线末尾标 `待确认`。两个来源各自给出候选：

| 来源 | 建议 | 拼音 | 接受后落到 | 置信度 |
| --- | --- | --- | --- | --- |
| 步骤原文 | 抵扣布丁螺丝 → 底壳固定螺丝 | 0.84 | step-004 安装底壳固定螺丝并预锁紧 | 0.75 |
| 步骤原文 | 紧抵扣布丁螺丝 → 移除底壳固定螺丝 | 0.72 | step-001 移除底壳固定螺丝 | **1.00** |
| ~~词库~~ | ~~紧抵扣 → 进气口~~ | ~~0.88~~ | — | — |
| ~~词库~~ | ~~抵扣布丁螺丝 → 底座锁定螺丝~~ | ~~0.79~~ | — | — |

两点都值得注意。第二条的结果置信度是满分 1.00，比正确答案的 0.75 还高，**按分数选就会选错**；而报幕明说「再次锁紧」，语义上不可能是「移除」。词库那两条（含拼音 0.88、分数最高的 `进气口`）已被同跨度规则丢弃：它们在教程里根本不存在，永远匹配不到步骤。这条素材的候选数因此从 6 降到 2，正确答案排在第一。接受它之后，素材从「待确认」变成正确匹配。

### 确认流程

```powershell
# 1. 分析后，把每条 decision 改成 accept 或 reject（可在 decision_note 写理由）
#    文件：<output>\lexicon-review.json
# 2. 加 --reuse-takes 重跑，跳过语音识别，几秒生效
```

两个重要性质：

- **可撤回。** 每次都从纠错前的原文重新应用，把 accept 改回 reject 会恢复原始识别文本，不留残留。
- **决策持久。** 已判定的提案即使不再被重新生成也会保留在文件里。否则接受后错误片段已经消失，下次重跑会静默回滚这条修复。

`run-job.ps1` 在有待确认提案时会停在生成草稿之前，因为此时时间线还可能变化，先做的草稿只会白做。用 `-SkipLexiconReview` 可以跳过。未安装 `pypinyin` 时自动退回只比字形，并在 `review.md` 提示。

## 素材匹配与排序规则

证据优先级：

1. 用户提供的人工修正；
2. 开始口令后、确实与 Wiki 有关的步骤口播；
3. 仅在口播为空或与 Wiki 无关时，使用有意义的文件名和明确分段编号；
4. Wiki 顺序和相邻步骤只用于辅助审核，不能代替缺失的口播和文件名。不抽帧、不做画面 OCR。多个步骤都达标时，优先匹配共享词更多的具体步骤，避免短步骤抢走更完整的报幕。

时间线规则：

- 按 Wiki 步骤顺序排列；
- 同一步的重复 take 全部保留；
- `第1段`、`第2段`、`01`、`02` 控制同一步内部顺序；
- 边界不清楚时加入 `待确认`；
- 文件名和口播冲突时写入报告，不会静默覆盖；
- 未匹配素材统一放到时间轴末尾；
- 没拍到的 Wiki 步骤只写入 `review.md`，不会插入假画面。

## 剪映 10/11 可编辑草稿

把一个普通文件夹复制到剪映草稿目录，并不一定会在首页显示。当前剪映至少要求：

1. 原生时间线 `draft_content.json`；
2. 项目 ID 一致的 `draft_meta_info.json`；
3. 使用本机当前剪映 `videoeditor.dll` 生成的加密内容；
4. 在 `root_meta_info.json` 中注册正确的草稿路径和项目 ID。

本 Skill 会完成这四项。剪映自动更新后可能删除旧版本 DLL；如果用户提供的旧版本目录已经失效，脚本会搜索同级版本目录并自动选择最新的有效安装。

当前实现已经在剪映 `10.6.0.14057` 和 `11.1.0.14287` 上完成验证。其他 10.x/11.x 版本会尽量调用对应安装版本自己的 DLL；未来新的大版本如果修改私有草稿格式，可能需要更新 Skill。

### 两阶段安全流程

兼容性 staging 不必每次都跑。用指纹判断剪映或写库是否变化：

```powershell
& "$Skill\.venv\Scripts\python.exe" "$Skill\scripts\roughcut.py" fingerprint
```

指纹包含注册表版本、安装目录、`videoeditor.dll` 大小/修改时间和写库版本。与上次记录一致就直接注册；变化后才自动补验一次。也可先手动生成不写首页索引的测试草稿：

```powershell
& "$Skill\.venv\Scripts\python.exe" "$Skill\scripts\roughcut.py" jianying10 `
  --plan "E:\本次拍摄\粗剪输出\edit-plan.json" `
  --drafts "E:\本次拍摄\剪映测试" `
  --name "兼容性测试"
```

验证后，保存剪映里的工作并完全退出剪映。然后注册正式项目：

```powershell
& "$Skill\.venv\Scripts\python.exe" "$Skill\scripts\roughcut.py" jianying10 `
  --plan "E:\本次拍摄\粗剪输出\edit-plan.json" `
  --drafts "D:\software\JianyingPro Drafts" `
  --name "Wiki自动粗剪" `
  --user-data "$env:LOCALAPPDATA\JianyingPro\User Data"
```

只有自动发现不了自定义安装目录时，才补充：

```text
--install-dir "D:\software\JianyingPro"
```

### 「注册」到底做了什么

注册完全是本机行为，不涉及账号、授权和任何联网请求。加上 `--user-data` 后，脚本会：

1. 创建 `<草稿目录>\<名称>\`，其中包含 `draft_content.json`（时间线）、`draft_meta_info.json`（项目 ID 和素材引用）以及剪映需要的辅助文件。
2. 调用你已安装剪映的 `videoeditor.dll` 加密这两个 JSON，让字节格式正好是那个版本能读的。
3. 修改之前，先把 `<用户数据>\...\root_meta_info.json` 备份到 `<草稿目录>\.roughcut-backups`。
4. 往索引里追加一条记录：草稿路径、项目 ID、名称和时间戳。剪映首页列的就是这个索引——没有登记的文件夹，内容再正确也不会显示。

不传 `--user-data` 时，第 1、2 步照做，第 3、4 步不做，这正是 staging 草稿安全的原因。

安全保护：

- 剪映还在运行时拒绝写入首页索引；
- 正式注册前自动备份 `root_meta_info.json` 到草稿根目录的 `.roughcut-backups`；
- 测试草稿使用隔离的临时 User Data，不会误出现在真实首页；
- 默认不覆盖同名草稿，只有明确使用 `--allow-replace` 才允许替换；
- 不修改原始视频，也不修改其他剪映项目。

## Final Cut Pro 使用方法

Final Cut Pro 使用通用 `timeline.fcpxml`，不需要剪映加密和首页注册。

1. 正常运行素材分析，并保持原始 MP4/MOV 路径不变。
2. 在 Final Cut Pro 选择 **文件 → 导入 → XML**。
3. 选择输出目录中的 `timeline.fcpxml`。
4. 打开导入后名为 `Wiki Rough Cut` 的事件或项目。
5. 检查每个源素材切割点；如果分析后移动了素材目录，需要重新链接媒体。
6. `文档字幕` 和 `待确认` 会作为不同标题层，可分别修改或删除。
7. 如果需要真正的字幕角色而不是标题片段，可以按自己的字幕流程另外导入 `wiki-subtitles.srt`。

FCPXML 只引用原始素材，不包含压平视频。生成后移动或重命名素材，Final Cut Pro 可能要求重新链接。`review-preview.mp4` 只是 720p 审核文件，不能替代可编辑 XML 时间线。

## 语音识别模型

只支持多语言 `faster-whisper small`。不会提供识别质量较差的 tiny 兜底。

语音识别没有一个适用于所有素材的固定准确率，麦克风距离、环境噪声、音量、口音和专业词都会影响结果。对这个 Skill 来说，最重要的是“简短报幕能否匹配到正确教程步骤”，并不要求随口说的每个字都完全正确。购买云端 API 前，建议先用本地模型测试 10～20 条真实素材，其中包含安静、嘈杂、含糊和带专业词的样本。

如果本地效果不足，先缩短报幕、在开始口令后立即说步骤名、让麦克风靠近一些，并用有意义的文件名作为独立证据。方言或专业术语仍不理想时，再考虑支持热词或上下文提示的云端 ASR。具体测试方法和云端选择见 [speech-recognition.md](skills/rough-cut-wiki-video/references/speech-recognition.md)。

完整安装会把模型下载到：

```text
skills/rough-cut-wiki-video/assets/models/faster-whisper-small/
```

如果模型丢失或文件不完整，只需要运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\download-model.ps1
```

官方下载页面：[Systran/faster-whisper-small](https://huggingface.co/Systran/faster-whisper-small)

模型约 486 MB，并包含超过 GitHub 普通仓库 100 MiB 限制的文件，因此不直接提交到 Git 历史。下载脚本会从官方来源下载一次，并检查运行所需文件是否完整。

## 命令说明

### 检查能力

```powershell
python scripts/roughcut.py doctor --json
```

### 分析并生成通用输出

```text
roughcut.py run
  --media 素材目录
  --wiki 教程步骤文件
  --output 输出目录
  [--mode auto|filename]
  [--model small]
  [--language zh]
  [--workers 6]
  [--batch-size 2]
  [--chunk-length 10]
  [--cpu-threads N]
  [--lexicon glossary.txt]
  [--review-confidence 0.70]
  [--preview]
  [--corrections corrections.json]
  [--reuse-takes]
  [--no-probe]
```

`auto` 使用语音、文件名、Wiki 顺序等证据。普通识别故障可以退回其他证据；缺少 `small` 模型属于安装问题，会显示一条修复命令。`filename` 完全跳过语音识别，并保留每个文件的完整时长。两种模式都不抽帧 OCR。

### 查看剪映/写库指纹

```text
roughcut.py fingerprint
  [--install-dir PATH]
  [--drafts DRAFT_ROOT]
```

### 生成或注册剪映项目

```text
roughcut.py jianying10
  --plan edit-plan.json
  --drafts 剪映草稿根目录
  --name 项目名称
  [--install-dir 剪映版本目录或安装根目录]
  [--user-data 剪映用户数据目录]
  [--allow-replace]
```

测试阶段不要传 `--user-data`。正式注册前必须完全退出剪映。

## 输出文件说明

一个完整任务目录长这样。只有 `output/` 是 `run` 命令生成的，其余要么是你的输入，要么是任务脚本写的状态。

```text
jobs/<任务名>/
├── wiki.md              输入，手写或由 -WikiText 生成
├── corrections.json     输入，可选，一次性
└── output/
    ├── wiki-source.md
    ├── wiki-steps.json
    ├── takes.json
    ├── edit-plan.json
    ├── review.md
    ├── lexicon-review.json
    ├── wiki-subtitles.srt
    ├── review-subtitles.srt
    ├── timeline.fcpxml
    └── review-preview.mp4
jobs/.roughcut-state/
└── jianying-fingerprint.json   状态，保留
```

### 必须要看的

- `review.md`：第一个要打开的文件。缺失步骤、`待确认` 素材、证据降级情况、待确认与已生效的术语纠错，以及时间线摘要。
- `lexicon-review.json`：待确认的术语纠错提案，需要逐条判断后重跑才生效，见 [两层术语纠错](#两层术语纠错)。判定结果会被保留，所以这个文件在任务期间不要删。
- `review-preview.mp4`：可选 720p 预览，用于快速肉眼核对，不是可编辑母版。

### 值得保留的

- `edit-plan.json`：真正的事实来源，包含生成时的 `skill_version`，以及与软件无关的入出点、顺序、字幕和匹配状态。其他产物都能从它重新生成，而且它不受剪映格式变化影响。
- `timeline.fcpxml`：Final Cut Pro 和兼容软件的可编辑交换文件。
- `wiki-subtitles.srt`：根据教程步骤润色后的正式字幕。
- `jianying-fingerprint.json`：记录已校验通过的剪映指纹。删掉也不会出错，只是多跑一次 staging 校验。

### 中间产物，可以删

- `wiki-source.md`：原样保存的教程步骤输入，留作追溯。
- `wiki-steps.json`：结构化步骤和字幕事实。
- `takes.json`：逐文件的媒体信息、口播标签、入出点、词库纠错痕迹和警告。如果打算用 `--reuse-takes` 重跑，建议保留——正是它让你能跳过语音识别。
- `review-subtitles.srt`：只有 `待确认` 字幕，审核完就可以删。

### 会自动清理的

临时 WAV 音轨在识别后删除；staging 草稿在校验通过后立即删除。`root_meta_info.json` 的备份会在 `<草稿目录>\.roughcut-backups` 里累积，确认草稿都能正常打开后可以自行清理。

通用分析命令不会再创建名为 `jianying-draft` 的目录。旧式明文目录很容易被误当成正式草稿复制，但无法在当前剪映首页正常显示。需要剪映项目时，必须单独运行 `jianying10`，生成真正加密并注册的项目。

## 常见问题

### 剪映首页找不到项目

- 检查正式生成时是否传入 `--user-data`；只复制测试目录不会注册首页。
- 检查 `root_meta_info.json` 中是否存在正确项目路径。
- 完全退出并重新打开剪映。
- 不要把整个粗剪输出外层目录复制到剪映草稿目录。

### 首页有卡片，但项目打不开

- 确认草稿使用当前实际安装版本的 DLL 加密。
- 用 `--install-dir` 指向剪映安装根目录，脚本会选择最新版本子目录。
- 保留诊断文件，需要时恢复 `.roughcut-backups` 中的首页索引。

### 提示缺少语音模型

运行 `scripts/download-model.ps1` 或 `scripts/download-model.sh`。不要改用 tiny；这个工作流明确不支持低质量兜底。

### 步骤口播识别不准

- 开始口令后立刻说更短的步骤名；
- 用简短动作名和分段编号重命名文件；
- 用 `--lexicon` 提供术语表做识别后纠错（不走 hotwords，避免 223 token 静默截断）；同音错字要靠第二层拼音提案，见 [两层术语纠错](#两层术语纠错)；
- 提供 corrections JSON 作为最高优先级人工修正；
- Wiki 与口播尽量使用一致的部件名称。
- 默认固定 `--language zh`；确认不是中文素材时才传 `--language ""`。

### 素材没有音轨或只想按文件名剪

使用 `--mode filename`。由于没有语音切割点，脚本会保留源文件完整长度。

### 缺少 FFmpeg

Windows：

```powershell
winget install --id Gyan.FFmpeg -e
```

禁用媒体探测后仍能生成基础计划，但准确时长和预览能力会受限。

## 隐私、安全和限制

- 语音识别在本地运行；不抽帧 OCR。
- 不依赖某个固定云端模型 API。
- 原始 MP4/MOV 只读，不会被覆盖。
- 这是粗剪工具，不代替最终人工剪辑判断。
- 完全没有教程相关口播且没有有效文件名的纯视觉素材仍会导出：完整放在时间线末尾，标记 `待确认`，并写入 `review.md`；原始文件不会被重命名。
- 剪映私有草稿格式可能继续变化，因此始终保留 SRT、FCPXML 和 `edit-plan.json`。
- 发布视频前需要人工检查字幕、安全提示、数量和安装方向。

## 许可证

本仓库使用 MIT 许可证。第三方包和模型保留各自许可证，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
