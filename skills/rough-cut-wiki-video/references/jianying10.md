# 剪映 10/11 原生草稿

## 首页不显示的原因

当前剪映项目同时依赖：

1. 原生 `draft_content.json` 时间线；
2. ID 一致的 `draft_meta_info.json`；
3. 本机当前版本 `videoeditor.dll` 可读取的加密；
4. 用户数据目录 `Projects/com.lveditor.draft/root_meta_info.json` 中的首页注册条目。

只复制通用输出包、旧版 `draft_info.json`、未加密 JSON 或未注册项目目录，都可能不显示。

## DLL 版本恢复

剪映更新器可能在退出后删除旧版本 DLL。导出器先检查用户指定的精确目录；如果失效，则搜索其同级版本、草稿根目录旁的 `JianyingPro` 目录和常见安装位置，选择版本号最高且确实包含 `videoeditor.dll` 的目录。

## 两阶段流程

先生成隔离测试草稿：

```powershell
python scripts/roughcut.py jianying10 `
  --plan "E:\任务\output\edit-plan.json" `
  --drafts "E:\任务\jianying-staging" `
  --name "兼容性测试"
```

不传 `--user-data` 时，库的默认 `%LOCALAPPDATA%` 行为会被隔离到临时目录，绝不能写入真实首页。

保存工作并完全退出剪映后，正式注册：

```powershell
python scripts/roughcut.py jianying10 `
  --plan "E:\任务\output\edit-plan.json" `
  --drafts "D:\software\JianyingPro Drafts" `
  --name "Wiki自动粗剪" `
  --user-data "$env:LOCALAPPDATA\JianyingPro\User Data"
```

自定义安装位置无法自动发现时增加 `--install-dir "D:\software\JianyingPro"`。

## 安全要求

- 检测到 `JianyingPro.exe` 运行时拒绝正式注册；
- 写入前备份 `root_meta_info.json` 到草稿根目录 `.roughcut-backups`；
- 默认拒绝覆盖同名项目；
- 不修改已有草稿、应用程序 DLL 或原始素材；
- 注册后解密回读，确认内容/元数据/首页 ID 一致；
- 验收视频片段数量、两条文字轨、源素材入出点和总时长。

## 界面验收

重新打开剪映后检查：

- 首页出现新项目；
- 主轨包含独立片段，可向前或向后回拉；
- 原声正常；
- `文档字幕` 和 `待确认` 可分别编辑或删除；
- 素材引用原始 MP4/MOV，而不是压平的审核预览。
