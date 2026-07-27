# rough-cut-wiki-video

[English](README.md) | [简体中文](README.zh-CN.md)

[![Tests](https://github.com/yinbaozong/rough-cut-wiki-video/actions/workflows/test.yml/badge.svg)](https://github.com/yinbaozong/rough-cut-wiki-video/actions/workflows/test.yml)

`rough-cut-wiki-video` 是一个可分享、平台无关的 Agent Skill。它会读取 MP4/MOV 素材文件夹和一份 Markdown 教程，把素材整理成可继续编辑的教学视频粗剪。主要适用于 3D 打印机安装、维护、零件更换、故障排查、开箱及其他分步骤教程。

Skill 会综合分析录制口令、简短步骤口播、文件名、Wiki 步骤顺序、可选 OCR 和素材时间。它不会修改原始 4K 文件，可以输出通用剪辑计划、可编辑字幕、SRT、FCPXML、审核预览，以及 Windows 剪映 10/11 能直接显示并编辑的原生加密草稿。

## 目录

- [可以生成什么](#可以生成什么)
- [支持平台](#支持平台)
- [安装](#安装)
- [快速使用](#快速使用)
- [工作原理](#工作原理)
- [录制视频时应该怎么说](#录制视频时应该怎么说)
- [Wiki Markdown 应该怎么写](#wiki-markdown-应该怎么写)
- [素材匹配与排序规则](#素材匹配与排序规则)
- [剪映 10/11 可编辑草稿](#剪映-1011-可编辑草稿)
- [Final Cut Pro 使用方法](#final-cut-pro-使用方法)
- [语音识别模型](#语音识别模型)
- [命令说明](#命令说明)
- [输出文件说明](#输出文件说明)
- [常见问题](#常见问题)
- [隐私、安全和限制](#隐私安全和限制)
- [开发和测试](#开发和测试)

## 可以生成什么

- 识别并删除 `三二一开始`、`321开始`、`321走`、单独一句 `开始` 等开拍口令。
- 识别并删除单独一句 `OK`、`过`、`可以`、`好了`、`结束` 等结束口令。
- 不会把 `开始拆卸`、`可以安装` 这类正常句子误判为口令。
- 一个视频文件中录了多组开始/结束口令时，可拆成多个 take。
- 同一个文件切换相邻步骤时，可根据 `下一步，移除支架` 进行粗分段。
- 能把 `安装侧板`、`移除支架` 等简短标签匹配到 Wiki 的详细步骤。
- 按 Wiki 步骤、明确分段编号和录制时间排序。
- 同一步的重复素材全部保留，不会静默挑选或丢弃。
- 正式字幕以 Wiki 为事实来源，不直接照抄随口说的内容。
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
- RapidOCR 和 ONNX Runtime：可选画面文字证据；
- 固定提交版本的高版本 `pyJianYingDraft`：用于剪映加密和首页注册；
- FFmpeg/ffprobe 检测。Windows 缺少 FFmpeg 时会显示 `winget` 安装命令。

只有在明确不需要语音识别、只想按文件名处理时，才选择 `core`：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1 -Profile core
```

### 第三步：检查环境

```powershell
.\.venv\Scripts\python.exe .\scripts\roughcut.py doctor --json
```

## 快速使用

最简单的方法是直接对 Agent 说：

```text
使用 rough-cut-wiki-video。
素材：E:\本次拍摄
Wiki 文件：E:\本次拍摄\教程.md
生成可编辑粗剪，并创建剪映草稿。
```

也可以直接运行：

```powershell
$Skill = "$HOME\.agents\skills\rough-cut-wiki-video"
& "$Skill\.venv\Scripts\python.exe" "$Skill\scripts\roughcut.py" run `
  --media "E:\本次拍摄\素材" `
  --wiki "E:\本次拍摄\教程.md" `
  --output "E:\本次拍摄\粗剪输出" `
  --mode auto `
  --preview
```

Wiki 默认是本地 `.md` 文件。你可以从网页、飞书、内部 Wiki 或其他文档复制正文，保存成 UTF-8 Markdown 后交给 Agent，不需要再抓取网页。

## 工作原理

自动粗剪严格按照证据处理，不会只凭 Wiki 顺序猜素材：

1. **读取 Wiki：** 从 Markdown 中提取有序动作、部件名称、数量、分支、工具、方向和安全说明。
2. **探测所有素材：** 使用 ffprobe 读取时长、音轨、分辨率和流信息。发现的每一个 MP4/MOV 都必须进入剪辑计划或明确的处理报告。
3. **优先分离音轨：** `auto` 模式下，FFmpeg 临时生成单声道 16 kHz WAV。原始视频不会被改写。
4. **本地语音识别：** faster-whisper `small` 生成多语言词级时间戳。开始/结束口令决定源素材切割点，开始口令后的短标签作为步骤口播。
5. **判断口播是否与 Wiki 有关：** 把口播与每个 Wiki 步骤比较。没有文字、只有无效语气词或与 Wiki 完全不相关的内容，不能作为匹配证据。
6. **必要时再检查文件名：** 没有有效口播时，从文件名提取动作、部件、顺序号和分段编号，再与 Wiki 匹配。
7. **没有证据就停止：** 口播和文件名都无法关联 Wiki 时，列出对应文件并要求用户补录步骤口播或重命名。不能用 Wiki 顺序或 OCR 掩盖缺少主要证据的问题。
8. **构建时间线：** 生成源素材入点/出点，按 Wiki 和分段编号排序，保留重复 take，冲突素材加入 `待确认`。
9. **生成字幕和通用输出：** 写出 Wiki 字幕、SRT、FCPXML、JSON 检查点和可选审核预览。
10. **生成剪辑软件项目：** Final Cut Pro 使用 FCPXML；Windows 剪映单独进行加密草稿生成和首页注册。

这个顺序可以避免最危险的错误：素材完全没有标签，却因为录制时间靠近某个 Wiki 步骤而被静默排到错误位置。

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

只需要说 Wiki 层级的大概动作名和可选分段编号：

- `安装背板，第1段`
- `移除背板`
- `打开卡扣，移除热端`
- `连接 AMS 电缆`

不需要讲清楚每一个手部动作，也不需要现场组织完整解说。最终教学字幕会根据 Wiki 补全和润色。

### 尽量避免这些内容

- 开始口令之后，不要先闲聊再说步骤名。
- 一条标签里不要同时说几个可能的步骤名称。
- 不要把结束词作为单独一句插在动作中间。
- 如果说错零件名，不要长时间自我纠正；直接停掉重新录一条更容易识别。
- 不要依赖 `DJI_0001`、`C0001`、纯时间戳等相机默认文件名表达步骤。

### 不说话时的文件名方案

如果不想录口令，可以把文件命名为：

```text
010_安装侧板_01.mov
010_安装侧板_02.mov
020_移除支架_01.mp4
```

文件名不用照抄 Wiki，简短但能理解即可。Agent 会根据 Wiki 语义寻找最接近的步骤。同一步的明确编号优先于录制时间。

## Wiki Markdown 应该怎么写

Wiki 是字幕事实来源。口播和文件名主要用来判断素材属于哪一步。

### 推荐结构

```markdown
# 更换热端

## 工具和准备工作

- H2.0 内六角扳手
- 关闭打印机电源，等待热端冷却。

## 操作步骤

1. 移除一颗螺丝，小心取下背板。
2. 打开卡扣，移除热端。
3. 小心放入新热端，然后闭合卡扣。
4. 安装并锁紧螺丝。

## 配置分支：已安装 AMS

1. 移除背板前，先断开 AMS 电缆。

> 注意：热端未冷却前不要触碰。
```

### Wiki 注意事项

- 需要出现在时间轴上的动作尽量使用有序列表。
- 一个编号步骤以一个主要动作目标为主；紧密相关的连续动作可以写在同一步。
- 写清部件名称、数量、工具规格、方向和注意事项。
- 工具、准备工作、安全提示使用独立标题；这些是字幕事实，不会自动变成素材步骤。
- 不同机型、不同 AMS 配置等互斥分支要有明确小标题。
- 图片有判断价值时，保留图片说明或 alt 文本。
- 能写出部件名时，不要只写“安装这个”“拆下它”。
- 不要加入没有依据的营销结论或安全结论。
- 文件使用 UTF-8 编码；支持中文文件名和中文路径。

Agent 可以调整语序、补充主语和连接词，让字幕更适合朗读，但不能增加 Wiki 没有支持的零件、数量、数值、方向或安全结论。

## 素材匹配与排序规则

证据优先级：

1. 用户提供的人工修正；
2. 开始口令后、确实与 Wiki 有关的步骤口播；
3. 仅在口播为空或与 Wiki 无关时，使用有意义的文件名和明确分段编号；
4. Wiki 顺序、OCR、视觉上下文和相邻步骤只用于辅助审核，不能代替缺失的口播和文件名。

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

先生成不写首页索引的测试草稿：

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
  --wiki 教程.md
  --output 输出目录
  [--mode auto|filename]
  [--model small]
  [--preview]
  [--corrections corrections.json]
  [--reuse-takes]
  [--no-probe]
```

`auto` 使用语音、文件名、Wiki 顺序等证据。普通识别故障可以退回其他证据；缺少 `small` 模型属于安装问题，会显示一条修复命令。`filename` 完全跳过语音识别，并保留每个文件的完整时长。

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

```text
output/
├── wiki-source.md
├── wiki-steps.json
├── takes.json
├── edit-plan.json
├── review.md
├── wiki-subtitles.srt
├── review-subtitles.srt
├── timeline.fcpxml
└── review-preview.mp4
```

- `wiki-source.md`：原样保存的 Wiki。
- `wiki-steps.json`：结构化步骤和字幕事实。
- `takes.json`：媒体信息、口播标签、入出点、OCR 和警告。
- `edit-plan.json`：与剪辑软件无关的素材范围、顺序、字幕和匹配状态。
- `review.md`：缺失步骤、待确认素材、降级情况和时间线摘要。
- `wiki-subtitles.srt`：Wiki 润色后的正式字幕。
- `review-subtitles.srt`：`待确认` 字幕。
- `timeline.fcpxml`：Final Cut Pro 和兼容软件的可编辑交换文件。
- `review-preview.mp4`：可选 720p 审核预览，不是可编辑母版。

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
- 提供 corrections JSON 作为最高优先级人工修正；
- Wiki 与口播尽量使用一致的部件名称。

### 素材没有音轨或只想按文件名剪

使用 `--mode filename`。由于没有语音切割点，脚本会保留源文件完整长度。

### 缺少 FFmpeg

Windows：

```powershell
winget install --id Gyan.FFmpeg -e
```

禁用媒体探测后仍能生成基础计划，但准确时长和预览能力会受限。

## 隐私、安全和限制

- 语音识别和 OCR 在本地运行。
- 不依赖某个固定云端模型 API。
- 原始 MP4/MOV 只读，不会被覆盖。
- 这是粗剪工具，不代替最终人工剪辑判断。
- 完全没有 Wiki 相关口播且没有有效文件名的纯视觉素材会停止自动导出，并要求用户补录步骤口播或重命名文件。
- 剪映私有草稿格式可能继续变化，因此始终保留 SRT、FCPXML 和 `edit-plan.json`。
- 发布视频前需要人工检查字幕、安全提示、数量和安装方向。

## 开发和测试

运行测试：

```powershell
.\skills\rough-cut-wiki-video\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

验证 Skill 包：

```powershell
python "$HOME\.codex\skills\.system\skill-creator\scripts\quick_validate.py" `
  .\skills\rough-cut-wiki-video
```

本仓库使用 MIT 许可证。第三方包和模型保留各自许可证，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
