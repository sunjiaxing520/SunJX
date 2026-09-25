# 🔥 故障案例 3：COUNT 跑了十分钟，定位全表扫描

> 定位：基于 Hive 真实机制设计的纸面演练，不是本人生产经历。按 Hive 3.1.x、Tez 执行引擎编写；数据规模、执行计划和等待时间均为教学设定，没有真实测速结果。

## ⭐ 详细技术版

### 1. 背景：SQL 很短，不代表工作量小

一张未分区的业务事件表保存约一年数据，采用普通文本文件，字段是 `event_id BIGINT`、`user_id BIGINT`、`event_date STRING`。其中 `event_date` 已标准化为 `YYYY-MM-DD`。业务真正要查的是昨天条数，但最初直接发出了全表统计：

```sql
SELECT COUNT(*) FROM interview_ops.events_raw;
```

`COUNT(*)` 统计所有行，包含列值为 NULL 的行；不是 `COUNT()`，后者不是这里应写的 SQL。案例设定没有可用于直接回答该查询的完整可信统计信息，实际启动了 Tez 扫描任务。

🔥 **没有日期条件的全历史精确计数，即使改成分区表，通常仍要覆盖全历史数据；分区不是“自动只算昨天”。** 部分 COUNT 会走统计信息或存储格式元数据优化，不能断言每次必然逐行扫描。[SELECT 与分区裁剪](https://hive.apache.org/docs/latest/language/languagemanual-select/)、[统计查询优化配置](https://hive.apache.org/docs/latest/user/configuration-properties/)

### 2. 现象：十分钟还没结束，先分清排队还是扫描

演练设定：任务已获得资源，Tez 界面显示输入任务持续读取大量文件；运行约十分钟仍未结束。不要只看总耗时就认定“SQL 写错了”，先区分等待资源、真正计算、失败重试。

本例对照数据：队列等待很短，绝大多数时间在读取未分区历史数据；没有明显单个任务拖尾，先不把它当成数据倾斜。

### 3. 排查过程：需求 → 表结构 → 执行计划 → 实际输入

下面 SQL 在已连接目标 HiveServer2 的 Beeline 会话中执行；数据库和表名是教学示例，不提供搭环境步骤。

```sql
SET hive.execution.engine;
SET hive.compute.query.using.stats;
SHOW CREATE TABLE interview_ops.events_raw;
DESCRIBE FORMATTED interview_ops.events_raw;
EXPLAIN SELECT COUNT(*) FROM interview_ops.events_raw;
```

| 语句/关键词 | 用来确认什么 |
|---|---|
| `SET 配置名;` | 查询当前会话值，不带等号不会修改；确认执行引擎、是否允许统计信息直接答查询 |
| `SHOW CREATE TABLE` | 看表定义，确认有没有 `PARTITIONED BY` |
| `DESCRIBE FORMATTED` | 看存储位置、文件格式、表属性与统计信息，`FORMATTED` 表示格式化详细输出 |
| `EXPLAIN SELECT ...` | 看预计怎么执行；普通 EXPLAIN 不运行查询，不能拿估算行数当真实读了多少 |

**执行计划解读示意，字段名字和层级随版本变化，不是实机输出：**

```text
Tez task
  TableScan: interview_ops.events_raw
    Input: 全部历史文本文件
  Group By: 局部 count
  Reduce/汇总: 合并 count
```

`TableScan` 只是扫描算子名称，**看到这个词本身不能证明“全表扫描”**；分区裁剪后也可能有 TableScan。要结合表是否分区、输入路径/分区数以及 Tez 实际读入量判断。普通 EXPLAIN 的估算也可能受过期统计影响。[EXPLAIN 官方说明](https://hive.apache.org/docs/latest/language/languagemanual-explain/)

接着和业务确认：“需要全历史总数，还是昨天总数？”本例需要昨天，于是用下列语句形成**相同业务口径**的优化前基线：

```sql
EXPLAIN
SELECT COUNT(*)
FROM interview_ops.events_raw
WHERE event_date = '2026-09-24';
```

`WHERE` 过滤昨天的行，但旧表没有按日期分区，文本文件仍可能大范围读取后再过滤。**加条件先保证结果正确，建立匹配的分区布局才进一步减少要读的数据。**

### 4. 解决方案：新建分区表，把数据真正放进对应分区

**第一步，建立新的目标表。** `interview_ops` 数据库已存在；目标表名和 HDFS 目录事先确认没有占用。原表继续保留用于校验和回退。

```sql
CREATE EXTERNAL TABLE interview_ops.events_by_day (
  event_id BIGINT,
  user_id BIGINT
)
PARTITIONED BY (dt STRING)
STORED AS ORC
LOCATION '/warehouse/interview_ops/events_by_day';
```

| 关键词 | 大白话解释 |
|---|---|
| `CREATE EXTERNAL TABLE` | 创建外部表；数据生命周期单独管理，不能因为名字叫外部表就随便删目录 |
| `BIGINT` / `STRING` | 长整型 / 字符串 |
| `PARTITIONED BY (dt STRING)` | 按日期登记分区，日期是分区列，不再放进普通列定义 |
| `STORED AS ORC` | 用适合分析的列式文件格式；这是另一项可优化因素，不能把所有收益都算成分区的功劳 |
| `LOCATION` | 指定 HDFS 数据根目录；日分区通常形如 `dt=2026-09-24` |

分区就像先按日期把文件分进不同文件夹，再建立目录索引。查昨天时，只找昨天那一格。[建表与分区定义](https://hive.apache.org/docs/latest/language/languagemanual-ddl/)

**第二步，按业务日期迁移，不能只创建一张空表。** 以下只示范迁移一天。目标日期分区已确认可由原表重建，执行覆盖写可以让同一天重跑时避免重复追加；它确实会替换目标当天内容，生产要按变更流程处理。

```sql
INSERT OVERWRITE TABLE interview_ops.events_by_day
PARTITION (dt = '2026-09-24')
SELECT event_id, user_id
FROM interview_ops.events_raw
WHERE event_date = '2026-09-24';

SHOW PARTITIONS interview_ops.events_by_day;
```

`INSERT OVERWRITE TABLE` 重建目标数据；这里的静态 `PARTITION (dt=...)` 把范围限定为当天分区；`SELECT` 只提供两个普通列，分区值由前面的常量指定。旧表不受影响。`SHOW PARTITIONS` 确认 Hive 已登记该分区。以后需要的历史日期必须按同样口径回填，并让每日入库任务写到相应日期；**这段示例没有迁移整年数据**。[INSERT 与分区写入](https://hive.apache.org/docs/latest/language/languagemanual-dml/)

**第三步，SQL 明确使用分区列筛选。**

```sql
EXPLAIN DEPENDENCY
SELECT COUNT(*)
FROM interview_ops.events_by_day
WHERE dt = '2026-09-24';

EXPLAIN
SELECT COUNT(*)
FROM interview_ops.events_by_day
WHERE dt = '2026-09-24';
```

`DEPENDENCY` 用于观察输入依赖信息；在实际输出中核对输入分区只包含目标日期。普通 EXPLAIN 看算子和计划。教学预期如下，**不是保证逐字匹配的输出**：

```text
input_partitions -> interview_ops.events_by_day / dt=2026-09-24
输入路径范围     -> /warehouse/interview_ops/events_by_day/dt=2026-09-24
```

⭐ `WHERE dt='2026-09-24'` 才是清楚直接的裁剪条件；只筛别的日期字段或把分区列包在复杂函数里，不能想当然地认为一定能裁剪。即使只有一个分区，仍可能要读取这个分区内的数据。

**第四步，先校验结果，再比性能。**

```sql
SELECT COUNT(*) AS old_count
FROM interview_ops.events_raw
WHERE event_date = '2026-09-24';

SELECT COUNT(*) AS new_count
FROM interview_ops.events_by_day
WHERE dt = '2026-09-24';

ANALYZE TABLE interview_ops.events_by_day
PARTITION (dt = '2026-09-24') COMPUTE STATISTICS;
```

`AS` 给结果起名；先核对两个相同日期口径的计数，再抽查关键字段、空值和业务数据质量。`ANALYZE ... COMPUTE STATISTICS` 为指定分区收集统计，通常需要实际工作量，安排在合适时机；不要把采集统计本身当成免费的加速。

性能验收同时记录队列等待、执行时长、输入分区与实际读入量。案例可以说“目标是只处理当天数据”，**不能说“我把十分钟优化成十秒”**，因为这里没有实测。若业务确实要全历史总数，保持全历史语义；再评估可信统计信息、可校验的日汇总表或其他方案，不能靠加昨天条件偷换问题。

### 5. 预防措施

- ⭐ 对常见查询约定日期范围，检查计划是否读取预期分区。
- 入库时就按业务日期组织数据，处理迟到数据和重跑，避免重复计数。
- 对新分区维护统计，监控文件数、平均大小和扫描量；分区不是越细越好，过细可能制造大量小文件。
- 优化前后保持同一业务口径、相近资源条件，留下结果校验和性能记录。

## 🔥 面试口语版（200—300 字，可直接背）

> 我整理过一个查询优化的纸面案例，还没有生产实操。现象是一条统计行数的语句跑了十分钟。我会先区分排队时间和计算时间，再看表结构、执行计划和实际输入量。案例里业务只需要昨天的数据，但原来查了全历史，而且表没有分区。我先确认统计口径，再设计按日期分区的新表，把当天数据正确写入分区，查询时明确加上日期条件。接着核对输入分区只剩目标日期，并和旧表同一天的结果对账，再比较读取量和耗时。需要强调的是，如果业务就是要全历史精确总数，不能只查昨天来冒充优化，分区表也不会自动减少全历史统计范围。后续把日期过滤、分区入库和统计维护做成规范。

**背诵线索：区分排队 → 查需求 → 看计划与输入 → 分区且正确迁移 → 同口径验证。**

## 版本与来源

核对日期：2026-09-25。演练 SQL 面向 Hive 3.1.x + Tez；Apache 文档为维护中的综合手册，含其他版本新增特性，本文只使用 3.1 已支持的基本建表、静态分区、EXPLAIN 和统计语法。未进行集群实测。

- [SELECT 手册](https://hive.apache.org/docs/latest/language/languagemanual-select/)：WHERE 与分区裁剪。
- [EXPLAIN 手册](https://hive.apache.org/docs/latest/language/languagemanual-explain/)：计划、输入依赖及实际执行的区别。
- [DDL 手册](https://hive.apache.org/docs/latest/language/languagemanual-ddl/)：分区表定义与统计信息。
- [DML 手册](https://hive.apache.org/docs/latest/language/languagemanual-dml/)：INSERT OVERWRITE 和分区写入。
- [Hive 配置说明](https://hive.apache.org/docs/latest/user/configuration-properties/)：`hive.compute.query.using.stats` 的统计查询优化。
