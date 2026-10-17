# status 报告约定

运行 `scripts/xmemory.py --root <记忆根> status --summary` 查看清点与待检查项，精简输出的 `objects` 每条占一行；去掉 `--summary` 查看完整对象列表。退出码 0 表示生成了报告，2 表示库或配置无法读取；结构问题保留在报告中。

## 范围与计数

程序只读指定根内的配置与 Markdown，检查库内相对链接；不检查外部客户端、数据库、Skysight 原件或外部链接可达性。相对链接越出根或经过符号链接时报告 `unchecked_link`，不访问目标。不创建根、缓存、锁、运行状态或修改文件。`.xmemory/backups/` 不参与有效内容检查，遗忘技能另行处理备份。

数量取 `inventory`，按下面单位汇报：

| 单位 | 取得方式 | 含义 |
|---|---|---|
| 配置来源 | `configuration.sources` / `enabled_sources` | 配置项数量及启用项数量，不是来源文件数 |
| 登记项目 | `configuration.projects` / `projects_with_records` | 登记项数量及已有记录声明归属的登记项目数量 |
| 已有对象 | `existing_objects` | 本次成功读取并识别路径类型的文件数，含元数据有问题的文件 |
| 库内记录 | `records.total`、`by_directory`、`by_source` | 记录总数、记录目录与来源分布；另列 partial、未定项目、未知来源时间、未配置来源、判为 unknown 的记录数，以及未被已有日文件或项目索引引用的记录数（`unlinked.daily` / `unlinked.projects`，按记录去重）；无效来源值不回显 |
| 已有派生对象 | `derived.total` / `by_kind` / `by_assessment` | 日总结、主题、索引、意识、画像与全局摘要的文件数，以及 current、stale、review、unknown 各多少 |
| 候选目标 | `candidates.total` / `by_kind` | 有直接输入、尚未创建的派生文件；是否有内容值得创建由 AI 判断 |
| 外部来源文件 | 读取器或文件工具列出的实际身份 | status 不扫描；只在外部清点完整时给总量 |
| 原生会话 | 读取器返回并核实的完整身份 | 原始会话记录按“会话 × 日”拆分，不能直接用记录份数代替会话数 |

`inventory.scan_complete` 为 false 时，文件读取或格式识别有缺口，已有对象计数只覆盖可检查部分。配置无效时 `inventory` 为 null，不能解读成空库。

`counts.objects` 仍汇总报告中各 assessment 的条数，包含记录和候选；不能作为已存文件数或完成率分母。覆盖比例仅能使用相同单位的完整身份清单，例如“列出的 20 份来源文件中，15 份已有版本与覆盖一致的记录”。没有完整外部清点时不报总体完成百分比。

## 报告字段

JSON 不保存到记忆库：

| 字段 | 内容 |
|---|---|
| `schema` | `xmemory/status-v1.5`，沿用现有格式 |
| `root`、`timezone`、`now` | 本次根、时区与系统时间；实际保存文件时重新取当前时间 |
| `inventory` | 上述配置、已有内容、候选清点及扫描完整性 |
| `objects` | `path`、`kind`、`updated`、`assessment`、`reasons`、`newer_sources`、`unlinked_sources`、`size_bytes` |
| `source_hints` | 配置来源的记录数、`latest_source_updated`、`latest_record_updated`、partial 数；`external_checked` 固定 false |
| `issues` | `code`、库内 `path`、可用行号或字段；秘密只报告定位和类型 |
| `counts` | 全库对象判断与问题类型的计数，精简输出仍保留完整计数 |

`--summary` 省略 current 且没有未链接来源的派生对象，以及只有 `external_source_not_checked` 的正常记录。保留过期或未知主题、带未链接来源的索引、异常记录、全部问题及有来源的候选。精简列表长度不等于 `counts.objects` 的总条数。

## 对象判断与动作

| 信号 | 含义 | 动作 |
|---|---|---|
| `newer_sources` | 直接来源的库内 `updated` 晚于对象；缺失对象列出全部已有输入 | 读取具体路径，核对新事实、更正与范围 |
| 已有日文件的 `unlinked_sources` | 当天 `day` / `event_days` 的记录尚未被该文件引用；使有效日文件 stale | 核对当天遗漏并补入来源，按采集日归档的导入每条一行列入“历史资料归档（事件日期未核实）”；保存前完成该文件全部待更新记录 |
| 项目 / personal 索引的 `unlinked_sources` | 该范围记录未被任何范围内文件引用；只列在已有索引上，作提示，不改变 assessment | 复核是否应纳入项目内容；确认不提炼的记录列入索引“参考记录”并写原因，不为消除提示强行提炼 |
| 主题 stale、索引 current | 主题引用的记录仍有更新，索引保存没有完成主题整理 | 继续处理该主题；检查范围包含所有主题，不能只看索引 |
| `candidate_target` / missing | 对象缺失但存在直接输入，输入见 `newer_sources`；不另列 `unlinked_sources` | 有实际内容才创建，登记项目本身不生成空候选 |
| `external_source_not_checked` | 记录固定判为 review，因为 status 不检查库外来源 | 采集时另核对来源版本与覆盖；汇报保留该 review，与派生对象 current 分开，不把每条提示当作失败 |
| `unknown_source_time` | 记录明确写了允许的空 `source_updated`，无法按来源时间比较 | 回查来源；只提示该记录，不使下游 unknown |
| `partial_source` | 记录存在声明过的读取缺口 | 续读或明确保留缺口，不把保存时间当作覆盖完成 |
| `incomplete_metadata_or_scan` / unknown | 对象、输入元数据或扫描有阻断问题 | 先查 issues；空的来源列表不能用于断言已完成 |

未链接检查只反映本次链接关系。已经链接的记录发生更正，仍靠文件时间比较；整份日文件或主题只改一部分后保存会遮住其他已链接更正。因此保存前按对象工序处理完整待更新范围。`current` 只是本次机械比较未发现变化，查阅仍需核对相关记录中的更正。

日总结按 `event_days` 明确列出的日期生成候选，省略时沿用 `day`，不展开连续日期。未定项目记录（`projects: []` 且 `project_status: "unresolved"`）参与日期、来源计数与画像复查，不进入 personal 索引或意识。记录归属或日期更正后，已有引用继续参与比较。

主题比较其引用的库内来源；项目索引比较项目记录与各主题；意识比较项目记录，画像比较记录；全局摘要比较已有意识、索引和画像。程序不推断语义支持关系。摘要另有 `upstream_updates`：已有画像、意识或索引出现明确 `newer_sources` 时，摘要增加 `upstream_newer_sources` 并提示 review；记录固定的外部复查提示不向上传播。

Skysight 直接写日总结，不生成记录。status 不检查活动块、末尾来源说明或外部窗口，活动覆盖由技能与实际原件核对，来源记录数为零不表示活动未整理。

## 结构问题

- `broken_link`：库内 Markdown 目标不存在；核对移动、命名或删除原因后修正。
- `unchecked_link`：相对链接越出记忆根或经过符号链接，目标未检查；从当前文件重算库内来源路径，不把它当作有效引用。
- `missing_field` / `invalid_field`：必需字段缺失或类型、身份、日期结构无法解释。`source_location` 始终必填。
- `invalid_time` / `future_time`：非空时间格式错误、无时区、缺少必需时间或晚于当前时间；继续影响下游判断。接受 `YYYY-MM-DDTHH:MM[:SS[.小数]]` 加 `Z`、`±HH:MM`、`±HHMM` 或 `±HH`，日期与时间之间也可用空格。仅 `source_updated: ""` 作为未知来源时间处理。
- `identity_review`：会话身份需核实；会话记录文件名末 8 位须对应至少一个已知原生 ID，其他记录目录不检查文件名。旧引用精确匹配，不自动迁移。
- `unresolved_project`：记录明确声明归属未定，按原件项目依据复核。
- `excluded_record`：仍有被排除会话的记录或可机械识别残留，按遗忘工序清理支持关系。
- `suspected_secret`：只报告文件、行号和类型，不输出值或邻近原文。
- `oversize`：全局入口超过 10,000 字节或意识超过配置上限；意识未配置上限时用 `limit_unset` 报告实际大小，不算超限。
- `read_error` / `unsupported_format`：存在读取或结构识别缺口，其他正常结果仍保留。

只读性通过调用前后文件清单、内容与修改时间快照验证。程序测试检查计数、候选、引用、时间传播、排除、秘密不回显及缺失根不被创建；模型的内容与行为另做评测。
