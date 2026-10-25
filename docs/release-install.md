# XMemory 1.8.0 安装说明

XMemory 1.8.0 包含三个 Skill，Client Readers 保持 0.2.1。分发包从 [GitHub Releases](https://github.com/BlueSkyXN/XMemory/releases) 下载。

| 包 | 内容 |
|---|---|
| XMemory-1.8.0.zip | 三端市场、XMemory 与 Client Readers 插件及说明 |
| XMemory-1.8.0-skills.zip | 三个技能入口、共享资源目录、可选只读脚本与许可证 |
| ClientReaders-0.2.1-skills.zip | 可按客户端选择的五个读取技能 |

按同名 `.zip.sha256` 核对归档；包内的 SHA256SUMS 用于核对文件。

完整市场包：Codex、Claude Code 将解压根作为市场来源；ZCode 使用其下的 plugins/。市场名 xmemory-marketplace，插件 ID xmemory@xmemory-marketplace，读取器独立安装。采用宿主当前支持的市场添加、安装或更新流程。

独立技能包：将 skills/ 下三个 xmemory-动作 入口目录与 xmemory/ 共享资源目录一起放入宿主技能目录，保留相对位置。xmemory/ 没有 SKILL.md，不是第四个技能。

更新旧安装后，在新对话确认只启用 xmemory-update、xmemory-recall、xmemory-note 三个 XMemory 入口；由客户端管理旧插件或旧独立技能，不直接改缓存登记。

正式记忆固定为用户 home 下的 `.agents/memory/`。基本读写使用宿主文件工具；Python 和 Client Readers 可选。旧试验内容不自动迁移或覆盖，启用前明确旧文件的处置。

读取告知模板位于 skills/xmemory/templates/agents-notice.md。将其合并到用户选择的宿主指令入口后，实际检查一个依赖历史的新任务能否读取相关记忆。外部定时和后台触发由宿主安排。

可选只读检查：

```bash
python3 -B /absolute/path/to/skills/xmemory/scripts/xmemory.py status
```

完整包内查看 plugins/xmemory/docs/install.md 与 usage.md；仓库资料见 https://github.com/BlueSkyXN/XMemory 。
