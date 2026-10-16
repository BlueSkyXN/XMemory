# 原生记忆与项目输出契约

Python 3.9+；只读本机，不联网、不调用模型、不写客户端、缓存或索引。维护源在 `tools/client_readers/`，技能内代码由同步工具生成。

## 命令与范围

```text
read.py projects [--since DATE] [--project PATH ...]
read.py memory locate [--project PATH ...]
read.py memory list (--store PATH | --project PATH) [--role ROLE ...] [--outline]
read.py memory read --path FILE [--section N | --text-offset N] [--max-chars N]
read.py memory search --query TEXT [--store PATH | --project PATH] [--role ROLE ...]
read.py doctor [--candidates]
```

`--project` 正向计算项目归属，不由目录 hash 反推项目。`--store` 必须是当前客户端发现的存储位置。`memory read` 只接受已知 store 内的记忆文件；越界或通向 store 外的文件链接报 `not_in_store`。备份默认只列元数据，不读正文；显式 `--include-backups` 才读取。`.git/`、`.DS_Store` 不参与结果。

默认 JSON，可用 `--format markdown`。列表、检索和总览默认每页 40 项，`--limit` 上限 200；按 `next_offset` 继续，不把单页当全量。`--role` 可重复或列多个值。`--since` 是会话最近时间的下界，不据记忆文件旧 mtime 删除候选。

## 共同信封

记忆 `schema=client-readers/memory-v1`，总览 `schema=client-readers/projects-v1`，自检 `schema=client-readers/doctor-v1`。

`client`、`data_root` 给出客户端与实际数据根。`warnings` 由全局告警与本页局部告警组成：`locate` 包含本页 store 及其下属文件的告警；`list/read/search` 只包含本页文件的告警。`warnings_outside_filter` 是其余已扫描局部告警的条数，包含因筛选或分页未返回的告警，按告警文字去重，不计提示。`projects` 将可归属的局部告警附在对应项目页，其余计入范围外数量。

全局告警保留 `source_unavailable`、`migration_ledger_unreadable`、`data_root_override_available` 等无法限定到条目的缺口；会话扫描告警先按来源文件记录，再按下表分配。局部告警还包括 `frontmatter_partial`、`memory_read_error`、`missing_index_target`、`outside_store_symlink`、`automation_config_unreadable`、`automation_cwds_invalid`。缺失索引目标归到索引文件，越界链接、目录中无法读取的文件及自动化配置问题归到 store。

| 客户端 | 记忆命令的会话扫描范围 | 会话扫描告警去向 |
|---|---|---|
| Claude Code | 只扫有 memory/ 的编码目录；指定 --store/--path 时只计算目标目录归属 | 挂到所在 store，并传给其文件条目，因为文件的 project 依赖该归属 |
| Qoder CN | CLI 按编码目录归属；旧分类仍依赖全部会话 cwd | CLI store 编码目录内的来源挂到该 store 及文件；其他目录、桌面库来源的告警为全局 |
| WorkBuddy | 全部会话 cwd，用于发现工作区 | 全局 |
| Codex | 只有 locate 扫描近期主会话头部 | 归属与 recent_injection 扫描中的告警挂到正规 codex-v1/codex-v2 store |
| ZCode | 沿用 SQLite 元数据读取 | 原有数据库读取告警保持全局 |

Claude 的记忆命令按编码目录在当前调用内复用扫描结果，不访问全量会话缓存。指定单文件或 store 时，其他 store 仍枚举文件并计算 SHA256，以保留 `duplicate_of`，但不计算其项目归属、不进入输出。`projects` 仍扫描全部会话；来源告警挂到该文件涉及 cwd 的项目行，没有产出任何 cwd 的来源告警保留为全局缺口。

`read` 的文件在正文读取期间失败时，保留文件元数据和告警，不返回 `text`；`search` 遇到同类失败时不返回该文件，改为一条全局 `memory_read_error: <path>`，使 `scan_complete=false`，且不重复计入 `warnings_outside_filter`。

`coverage.total_items` 是筛选后的总项数；`scan_complete` 仅在本页无缺口告警、全局无缺口且无下一页时为 true。`compressed_twin:` 为提示类前缀，不参与缺口判定；范围外局部告警也不降低本页覆盖率。`has_more`、`next_offset` 描述项目或文件分页，长正文继续使用 `next_text_offset`。

`memory locate` 另含 `summary={layout: {status: count}}`，按分页前全部选中的 store 汇总。Qoder CN 旧版每个分类仍独立列为 store。

`runtime` 给出当前 `python`、`executable` 和选用的 zstd 后端。会话仍保留历史 `schema` 值与引用格式；新字段不改变原引用。

## Store

每项含 `path`、`layout`、`scope`、`project`、`candidates`、`status`、`aliases`、`files`、`latest_mtime`、`near`、`recent_injection`。`project` 为 `{path,basis}`，无法唯一归属为 null；撞名的所有路径放在 `candidates`，不自动选择。`files` 不计备份。`aliases` 为同 inode 的 store 其他路径写法。`near` 只表示疑似正规目录，不是已认定归属。

- `layout`：`zcode-project`、`claude-project`、`codex-v1`、`codex-v2`、`codex-automation`、`workbuddy-workspace`、`workbuddy-user`、`workbuddy-persona`、`qodercn-cli-project`、`qodercn-desktop`、`qodercn-legacy`。
- `scope`：`project`、`global`、`user`。
- `status`：`ok`（有文件）、`empty`（唯一归属或全局位置无文件）、`orphan`（项目归属未知）、`ambiguous`（撞名）、`unmounted`（所在外置卷未挂载）、`unofficial`（非官方或停用位置）、`unsupported`（未知布局）。项目目录本身缺失不等于外置卷未挂载。
- `basis`：`zcode_path_hash`、`zcode_identity_hash`、`encoded_cwd`、`session_cwd`、`automation_cwds`、`project_arg`、`none`。没有唯一归属时 `project=null`，不伪造依据。

Codex V1/V2 正规 store 另有 `last_written`。仅 `memory locate` 计算 `recent_injection`，按最近 7 天主会话头部统计 `user`、`automation`，带 `days` 与 `checked_main_sessions`；无可查主会话时为 null。Codex 的 `memory list/read/search` 不读取会话。不以文件更新时间推定注入版本、双写开关或所有会话行为。

## Memory file

每项含 `path`、`rel`、`role`、`size`、`mtime`、`sha256`、`frontmatter`、`frontmatter_partial`、`native_session`、`project`、`indexed`、`duplicate_of`、`same_session_as`、`migrated`。

- `frontmatter` 支持顶层标量、行内简单列表、任意键下一层映射、块式标量列表、普通标量续写；嵌套子键同样支持续写和块式列表。缩进只用空格，空行与 `#` 开头的行跳过；块式列表各项缩进一致。普通标量不以引号或 `[` 开头时，后续更深缩进、非 `- ` 开头的行去首尾空白后以单空格连接，续写中的冒号保留。空值且没有更深行时为 `""`。旧分类目录名仍覆盖 `category`。
- `frontmatter_partial` 完整时为 `[]`；不支持 `|`/`>` 块标量、`{}` 行内映射、锚点/别名/标签（`&`、`*`、`!`）、两层以上映射、映射型列表项、跨行带引号字符串或制表符缩进。相应键不输出值，并记录键名（嵌套为 `parent.child`）；无法归属的行记为 `line:<N>`。重复键保留首次值，并记录该键。
- 每个文件最多一条 frontmatter 告警：`frontmatter_partial: <path>; keys=<k1,k2>; lines=<n>`，`lines` 为涉及不支持写法的非空、非注释行数。缺少结束分隔符时元数据为空，`frontmatter_partial=["line:1"]`，告警为 `frontmatter_partial: <path>; missing_delimiter`。
- `native_session={client,id,from}` 是线索，不能直接当已经核实的原生身份；Codex 摘要另保留头部 `rollout_path`。
- `indexed` 依据同 store 索引的 Markdown 链接或 `[[名称]]`；无索引为 null，有索引但未链接为 false。缺失目标进入 warnings。
- `duplicate_of` 列同客户端原始内容 SHA256 相同的其他文件；`same_session_as` 标同一原生会话的其他摘要；只标注、不合并。
- Qoder CN 命中目标账本时 `migrated={imported_at,unchanged}`；`unchanged` 比较当前字节 hash，不把迁移等同于独立来源。账本状态不明时不推断 imported/skipped 与生成文件的语义关系。

角色：`index`、`topic`、`consolidated`、`session_summary`、`raw_extract`、`daily`、`note`、`profile`、`persona`、`skill`、`automation`、`process_log`、`instructions`、`activity`、`backup`、`unknown`。同名 MEMORY.md 的角色以客户端布局为准。

`--outline` 返回 `section`（从 0 起）、`level`、`title`、`text_offset`；忽略代码围栏内标题。正文先完整遮蔽，再按字符偏移分页，默认 6000、最多 100000 字符。`--section N` 从该标题读到下一标题，`section_end` 给出该段终点；截断后用返回的 `next_text_offset` 继续，`--max-chars` 不超过 `section_end - next_text_offset`，以免展开到下一段。`text_chars` 是完整遮蔽后长度；`source_ref` 是实际文件路径。关键词为不区分大小写的字面检索，不是语义搜索。来源变化后应重新列出并核对 hash，不把不同版本的文本片段拼成完整读取。

## Projects

每项含 `path`、`aliases`、`exists`（true / false / `unmounted`）、`sessions={count,first,last}`、`memory={stores,files}`、`flags`、`parent`、`children`。按最近会话使用时间排序。未唯一归属的记忆不计入某一候选的文件数。

`parent` 为最近祖先项目行的主路径，比较时同时检查主路径及 aliases；宽根不参与父子关系，没有祖先时为 null。`children` 为 parent 指向本行的直接子项目数。两项均在 --project 筛选与分页之前计算，筛选后保留原值，供调用方按父项目分组。

`flags`：`case_variant`、`alias`、`collision`、`nested`、`broad_root`、`unmounted`、`memory_without_sessions`、`orphan_nearby`。等于自身 anchor 的文件系统根（含 Windows 盘符根）、用户主目录和 macOS 根目录下 Volumes 的直接子目录标为 `broad_root`，计算 `nested` 时既不作父目录也不作子目录。其余父子项目标为 `nested`。同 inode 的路径合为 aliases；不同 inode 的 worktree 与大小写变体并列，不替用户合并项目。Codex 会话元数据仅取首行 `session_meta`，中途切换目录不计入总览，精确归属用 `sessions read`。

## 运行环境

用用户自己的 `python3`；用户明确指定 `CLIENT_READERS_PYTHON` 时由调用方使用它。脚本不进入项目虚拟环境、不自行换解释器、不执行安装、升级或卸载。低于 3.9 报错停止。

zstd 固定顺序：`compression.zstd` → 已有 `backports.zstd` → 已有 `zstandard` → PATH 的 `zstd` → 常见前缀的 `zstd`。zstandard 先用空输入试调 `stream_reader(..., read_across_frames=True)`；探测期间出现任何 Exception 都视为该后端不可用并继续回退，实际读取也传该参数。前缀包括 Apple/Intel Homebrew、Linuxbrew、MacPorts；没有 Homebrew 也可使用 Python 后端。外部工具使用参数列表、超时、流式读取和退出码检查，不经 shell。全部缺失时给出 `zstd_missing`、未读数量与文字建议：指定已有 Python 3.14+；或 `python3 -m pip install --user backports.zstd`；或 macOS `brew install zstd`。由用户自行选择执行。

`doctor` 给出当前解释器来源、版本、包数、PEP 668 标记、选择依据、各可用后端及数据根状态。`--candidates` 只以 `-I -B` 启动已找到的其他解释器做探测，每个限时 5 秒；不用于自动切换。别名仅识别 shell 文件里的字面路径，不执行 shell 配置或动态表达式。TOML 先用已有 `tomllib`，Python 3.9 回退仓库已有的 TOML 子集解析器。
