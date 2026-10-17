# XMemory 源码仓库

这是 XMemory 与 Client Readers 的源码及评测仓库。用户问怎么使用、查看初始化现状、更新或补全记忆时，按已安装的 XMemory 技能和用户选定的记忆根执行；`status` 提供只读检查，记忆内容由技能维护。开发请求才修改本仓库。

## 目录与改动

- `plugins/xmemory/`：八个技能、参考、模板；运行代码只在 `skills/xmemory/scripts/`。
- `tools/client_readers/`：独立读取器源码；`plugins/client-readers/` 的脚本由工具生成，修改读取器时通过既有同步流程更新。
- `tests/`：程序、包与只读性检查；`evals/`：合成行为夹具和预先确定的判据。
- `local/`：私有计划、模型运行记录和证据，保持 Git 忽略；正式记忆与客户端配置不放入仓库。

客户端市场可能直接使用本仓库目录。开发前检查 worktree，行为改动在隔离工作区完成；正式库补全、客户端换装和发布按各自明确范围执行。

保持 Markdown 格式 `xmemory/v1.5`、八个技能入口和 `status` 的只读性。字段或行为变化同步参考说明及相应测试。单元测试覆盖机械结果，技能改动另用隔离合成库验证自然请求、实际写入、来源与范围；保留失败轮。

## 开发检查

开发工具需要 Python 3.11+；安装后的技能运行代码兼容 Python 3.9+，只用标准库。

```bash
python3 -B tools/check_package.py
python3 -B tools/build_client_readers.py --check
python3 -B -m unittest discover -s tests -v
python3 -B tools/build_release.py --output dist/<新目录>
```

检查触及范围的 diff 与产物。公开源码、文档、测试和提交只使用虚构数据或占位路径，不携带真实记忆、会话、凭据与私有环境信息。发布、客户端安装及真实记忆验收分别记录结果。
