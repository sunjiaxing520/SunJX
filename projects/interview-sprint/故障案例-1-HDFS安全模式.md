# 🔥 故障案例 1：磁盘写满，HDFS 进入安全模式

> 定位：基于真实机制编写的**纸面排障演练**，不是本人生产经历。环境按 Apache Hadoop 3.3.6、Linux 编写；所有日志、主机名、容量、路径都是教学示例。今晚先读口语版，再顺着命令理解原因，不需要搭集群或实际执行。

## ⭐ 详细技术版

### 1. 背景：先分清是哪块磁盘满了

某离线数仓每天往 HDFS 写入业务数据。NameNode 的本地元数据目录 `/data/hdfs/name` 和历史运行日志 `/data/log/hadoop-hdfs` 共用 `/data` 分区。日志轮转失效，旧日志挤满磁盘，NameNode 资源检查发现可用空间低于保留阈值，于是进入安全模式。

**一句话因果：NameNode 本地空间不足 → 触发保护 → HDFS 暂停修改。** 这与“DataNode 存业务块的盘满”不同；单个 DataNode 满了，不等于 NameNode 必然进入安全模式。该保护机制见 [Hadoop 默认配置](https://github.com/apache/hadoop/blob/rel/release-3.3.6/hadoop-hdfs-project/hadoop-hdfs/src/main/resources/hdfs-default.xml)。

### 2. 现象：读可能正常，写报错

客户端上传失败。以下为**按真实报错形式整理的示例片段，不是采集日志**：

```text
put: Cannot create file /warehouse/ods/new_batch.csv. Name node is in safe mode.
WARN FSNamesystem: NameNode low on available disk space.
```

补充观测：`/data` 的可用空间只剩约 40 MiB；本例保留阈值是 104857600 字节，即 100 MiB。不要把这个默认值当成适合所有生产环境的容量预警线。

🔥 安全模式可以理解成“先保护账本，暂停写入”。它会限制命名空间修改，也不会正常开展块复制、删除工作；**不是万能重启按钮，也不是所有故障的共同原因**。[安全模式说明](https://hadoop.apache.org/docs/r3.3.6/hadoop-project-dist/hadoop-hdfs/HdfsUserGuide.html)

### 3. 排查过程：状态 → 集群 → 主机 → 日志

以下命令在已有 Hadoop 配置和相应权限的 Linux 运维终端执行；本地磁盘命令在 NameNode 主机执行。

```bash
hdfs dfsadmin -safemode get
hdfs dfsadmin -report
hdfs getconf -confKey dfs.namenode.name.dir
hdfs getconf -confKey dfs.namenode.edits.dir
hdfs getconf -confKey dfs.namenode.resource.du.reserved
df -h /data
df -i /data
du -xh --max-depth=1 /data/log
tail -n 200 /data/log/hadoop-hdfs/hadoop-hdfs-namenode-nn01.log
hdfs fsck /warehouse/ods
```

| 命令与参数 | 大白话解释 | 本例如何判断 |
|---|---|---|
| `dfsadmin -safemode get` | 只问现在是否处于安全模式 | 返回 ON |
| `dfsadmin -report` | 看 DataNode 存活、容量、剩余空间等 | 节点全部存活、仍有 HDFS 剩余空间；**它不能替代 NameNode 本地磁盘检查** |
| `getconf -confKey 配置名` | 读取当前客户端配置中的指定值；再与服务端实际配置核对 | 找到元数据、编辑日志位置及空间阈值 |
| `df -h /data` | `-h` 以易读单位显示指定路径所在文件系统容量 | `/data` 接近 100% |
| `df -i /data` | `-i` 查看 inode，也就是文件数量额度 | 排除“容量还有但文件数量用尽” |
| `du -xh --max-depth=1 /data/log` | `-x` 不跨文件系统，`-h` 易读单位，深度 1 看下一层目录 | 发现历史 Hadoop 日志过大 |
| `tail -n 200 日志路径` | 读最后 200 行 | 找到空间不足告警，核对时间与上传失败时间 |
| `fsck /warehouse/ods` | 只检查指定业务目录的块健康，不带删除参数 | 本例没有丢块、坏块；大集群先查受影响目录，再看全局缺块指标 |

这一步的结论不是“磁盘满就强退”，而是：**DataNode 正常，故障落在 NameNode 本地日志挤占元数据卷**。若日志提示启动时块上报不足，就应改查 DataNode/块报告，不能套用此结论。[HDFS 命令参考](https://hadoop.apache.org/docs/r3.3.6/hadoop-project-dist/hadoop-hdfs/HDFSCommands.html)

### 4. 解决方案：先释放真正不足的空间，再恢复写入

**第一步，清理已确认过期且已归档的本机日志。** 本例已按保留制度确认下面这一个压缩日志可以删除，并确认它不再被进程写入。命令只是说明处理动作，真实环境应替换为已核实的精确路径。

```bash
ls -lh /data/log/hadoop-hdfs/archive/namenode-20260801.log.gz
rm -i -- /data/log/hadoop-hdfs/archive/namenode-20260801.log.gz
df -h /data
```

`ls -l` 看详细信息、`-h` 看易读大小；`rm -i` 删除前逐项确认，`--` 表示后面是文件名。这里只处理单个已归档日志，不能删除 `fsimage`、`edits`、`current` 或 DataNode 数据块目录。若没有可清文件，就扩容或迁移非关键日志，不能靠调低阈值掩盖问题。

**第二步，确认容量、资源告警和块健康恢复后再退出。** 本例资源型安全模式仍保持 ON，由管理员执行普通退出；启动型安全模式通常满足条件后会自动退出。缺块等问题没有恢复时，继续修复，不使用强制退出绕过保护。

```bash
hdfs dfsadmin -safemode get
hdfs dfsadmin -safemode leave
hdfs dfsadmin -safemode get
```

`leave` 请求正常退出；最后 `get` 应返回 OFF。**安全模式仍为 ON 时，不能用删除 HDFS 业务文件的办法释放空间；本例要释放的还是 NameNode 本地磁盘。**

**第三步，验证真实写入与读取。** 在已授权的测试目录执行：

```bash
printf 'hdfs probe\n' > /tmp/hdfs-probe-20260925.txt
hdfs dfs -mkdir -p /tmp/interview-healthcheck
hdfs dfs -put /tmp/hdfs-probe-20260925.txt /tmp/interview-healthcheck/probe-20260925.txt
hdfs dfs -cat /tmp/interview-healthcheck/probe-20260925.txt
```

`printf` 写一行本地测试数据；`>` 写入指定本地文件；`-mkdir -p` 创建目录并允许父目录已存在；`-put` 上传实际内容；`-cat` 读取验证。测试文件名应使用当次唯一名字，避免覆盖已有文件。验收看写入成功、读取一致、磁盘告警消失、关键任务恢复，不虚构“几分钟恢复”的实测成绩。[文件系统命令](https://hadoop.apache.org/docs/r3.3.6/hadoop-project-dist/hadoop-common/FileSystemShell.html)

### 5. 预防措施：本机日志和 HDFS 数据分开管

- ⭐ 对 NameNode 本地元数据卷、日志目录、inode 和增长速度做告警，日志设置轮转、保留期，并尽量分盘存放。
- 对业务 HDFS 目录设置空间和文件数配额，配合生命周期清理。**配额不能解决 NameNode 本地日志膨胀**，它防的是业务目录无限增长及小文件滥用。
- 保存故障时间线和恢复检查项；上线新日志策略后验证轮转真的生效。

```bash
hdfs dfsadmin -setSpaceQuota 300g /warehouse/ods
hdfs dfsadmin -setQuota 1000000 /warehouse/ods
hdfs dfs -count -q -h /warehouse/ods
```

`-setSpaceQuota 300g` 把示例目录空间上限设为 300 GiB；**复制块按副本计费**，三副本下可容纳的逻辑数据约为 100 GiB，不能直接当 300 GiB 原始数据。`-setQuota 1000000` 限制该树下文件和目录总数；`-count -q -h` 查看数量、配额及易读的空间信息。数值应根据现有使用量、增长与保留周期制定，不应照抄。[配额说明](https://hadoop.apache.org/docs/r3.3.6/hadoop-project-dist/hadoop-hdfs/HdfsQuotaAdminGuide.html)

## 🔥 面试口语版（200—300 字，可直接背）

> 我最近按官方文档整理过一个安全模式的纸面演练，还没有在生产环境处理过。场景是文件上传报安全模式错误。我会先查安全模式和集群报告，再看主节点的磁盘、日志和数据块健康。这个案例里，数据节点正常，真正原因是旧日志挤占了主节点的元数据磁盘，触发空间保护。我会先暂停新增写入，按保留规则清理已归档的本机日志，绝不删除元数据或数据块。确认空间和块健康恢复后，再正常退出安全模式，用小文件验证读写。后续补日志轮转、容量告警和业务目录配额。这里要分清，本机日志靠轮转管理，业务数据靠配额管理；不能看到安全模式就直接强退。

**背诵线索：报错 → 查两种空间 → 清本机旧日志 → 确认再退出 → 验证与预防。**

## 版本与来源

适用基线：Apache Hadoop 3.3.6；厂商发行版的目录、认证、告警阈值可能不同。命令与机制于 2026-09-25 核对，未在真实集群执行。本文是学习案例，不含真实生产故障数据。

- [Hadoop 3.3.6 HDFS 用户指南](https://hadoop.apache.org/docs/r3.3.6/hadoop-project-dist/hadoop-hdfs/HdfsUserGuide.html)：安全模式。
- [Hadoop 3.3.6 默认配置源码](https://github.com/apache/hadoop/blob/rel/release-3.3.6/hadoop-hdfs-project/hadoop-hdfs/src/main/resources/hdfs-default.xml)：NameNode 资源检查与空间保留阈值；仅用于核对，不要求阅读源码。
- [HDFS 命令](https://hadoop.apache.org/docs/r3.3.6/hadoop-project-dist/hadoop-hdfs/HDFSCommands.html)、[文件系统命令](https://hadoop.apache.org/docs/r3.3.6/hadoop-project-dist/hadoop-common/FileSystemShell.html)、[配额](https://hadoop.apache.org/docs/r3.3.6/hadoop-project-dist/hadoop-hdfs/HdfsQuotaAdminGuide.html)：命令参数依据。
