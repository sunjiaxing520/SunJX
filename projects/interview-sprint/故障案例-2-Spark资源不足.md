# 🔥 故障案例 2：YARN 队列占满，Spark 一直 ACCEPTED

> 定位：纸面排障演练，不是本人生产经历。基线为 Hadoop 3.3.6 Capacity Scheduler、Spark 3.5.7 on YARN。界面内容和资源数字均为教学示意，没有真实截图，也没有实际提交任务。

## ⭐ 详细技术版

### 1. 背景：任务提交成功，不代表已经开工

某集群可调度内存为 100 GiB，设 `root.prod` 和 `root.adhoc` 两个队列。临时分析队列 `adhoc` 的保证容量、最大容量都设为 20%，已有任务用完这 20 GiB。生产队列只用了 40 GiB，集群还空着约 40 GiB，但临时队列不能突破自己 20% 的硬上限。

此时提交新的 Spark 任务，连负责申请资源的 ApplicationMaster（AM，应用管家）都暂时拿不到容器，任务就留在 ACCEPTED。**本例假设没有用户限额、AM 限额或节点标签等第二重阻塞；真实排查必须检查。**

### 2. 现象：看起来“卡住”，其实在排队

提交终端反复显示以下**示意输出**：

```text
Application report for application_1790294400000_0042 (state: ACCEPTED)
Application State : ACCEPTED
Queue             : adhoc
```

打开 ResourceManager Web UI 的示例地址 `http://rm01:8088`。8088 是常见 HTTP 默认端口，实际集群可能启用 HTTPS 或自定义端口。**截图应看到的内容描述如下，不是伪造的生产截图：**

```text
Applications 页面
  ID: application_1790294400000_0042
  State: ACCEPTED    Queue: adhoc
  AM 尚未正常启动/注册，尚无可用的 Spark 应用页面

Scheduler 页面 -> root -> adhoc
  Configured Capacity: 20% of cluster
  Maximum Capacity:    20% of cluster
  Used Capacity:      100% of queue（约占集群 20%）
  Pending Applications: 有等待任务

集群总体：约 60 GiB 已用，40 GiB 空闲
```

🔥 UI 的“队列已用 100%”与“集群已用 100%”不是一回事，先确认指标分母。字段名字随 UI 版本可能不同，判断要结合具体数值和应用 Diagnostics。

### 3. 排查过程：先看 AM，再看 Executor

在有 Hadoop 配置、YARN 访问权限的 Linux 客户端执行：

```bash
yarn application -status application_1790294400000_0042
yarn application -list -appStates ACCEPTED,RUNNING
yarn queue -status adhoc
yarn node -list -all
```

| 命令及参数 | 看什么 |
|---|---|
| `application -status 应用ID` | 查状态、队列、诊断信息；先判定是不是资源等待 |
| `application -list -appStates ACCEPTED,RUNNING` | `-list` 列出应用，`-appStates` 只列指定状态；看同队列竞争情况 |
| `queue -status adhoc` | 查指定队列状态及容量信息；完整 AM/用户限制还要看 Scheduler UI |
| `node -list -all` | 列出全部 NodeManager，包括异常节点，检查是不是节点故障让可调度资源骤减 |

再按这个顺序比较：[YARN 命令依据](https://hadoop.apache.org/docs/r3.3.6/hadoop-yarn/hadoop-yarn-site/YarnCommands.html)

1. **队列有没有可用额度？** 本例集群有空闲，但 `adhoc` 达到最大容量，这是主因。
2. **AM 有没有自己的额度？** 查队列 AM 已用量、AM 上限、用户限制和应用诊断。`maximum-am-resource-percent` 限制 AM 资源比例，0.1 表示 10%；达到上限时，哪怕还有普通任务资源，也可能 ACCEPTED。
3. **某个节点能不能放下申请？** 集群空闲资源加起来够，不代表单节点能满足这一个 AM 容器；还要考虑节点标签、内存/CPU和最大分配限制。
4. **是否反复启动失败？** ACCEPTED 也可能出现在 AM 重试等情形，不能见到这个状态就直接改队列。查看 Diagnostics 和历史 attempt；AM 还没启动时没有 AM 日志是正常的。

⭐ 如果已经 RUNNING 但 Executor 数量不足，则继续查执行资源；这与本例“AM 还没启动”是两个阶段。AM 上限与并发限制的依据见 [Capacity Scheduler](https://hadoop.apache.org/docs/r3.3.6/hadoop-yarn/hadoop-yarn-site/CapacityScheduler.html)。

### 4. 解决方案：先协调，再调整真实限制

**第一步，先选低影响方案。** 若不紧急，等待现有任务完成或错峰；若紧急，和负责人确认能否释放低优先级任务、使用已授权的其他队列。不要随意杀掉别人的作业，也不要重复提交制造更多排队任务。

**第二步，本例经评估调整两个队列的配额。** 假设原配置是 `prod=80%`、`adhoc=20%`，且 `adhoc.maximum-capacity=20%`。在 ResourceManager 使用的配置目录编辑现有文件，下面是需要改动/核对的属性，**不是覆盖整份配置**：

```bash
cp -p "$HADOOP_CONF_DIR/capacity-scheduler.xml" "$HADOOP_CONF_DIR/capacity-scheduler.xml.before-interview-20260925"
vi "$HADOOP_CONF_DIR/capacity-scheduler.xml"
```

`HADOOP_CONF_DIR` 要已经指向 RM 实际使用的配置目录；`cp -p` 保留文件属性做备份，备份名需确认没有重名；`vi` 编辑文件。由管理平台生成配置的环境应在平台改，避免手改被覆盖。

```xml
<property>
  <name>yarn.scheduler.capacity.root.queues</name>
  <value>prod,adhoc</value>
</property>
<property>
  <name>yarn.scheduler.capacity.root.prod.capacity</name>
  <value>60</value>
</property>
<property>
  <name>yarn.scheduler.capacity.root.adhoc.capacity</name>
  <value>40</value>
</property>
<property>
  <name>yarn.scheduler.capacity.root.adhoc.maximum-capacity</name>
  <value>60</value>
</property>
```

`capacity` 是保证份额；本例两个兄弟队列相加必须是 100。`maximum-capacity=60` 允许临时队列在资源空闲且其他限制允许时最多用到 60%，不是立即给它 60%。`prod` 的既有最大容量须不低于新的 60% 保证容量。降低生产队列保证份额需要按实际服务要求评估，不能照搬演练数字。

**只有诊断明确命中 AM 上限**，才评估下面这个独立分支。例如原值 0.1，确实需要更多并发且能承受时，才改为 0.2；它不是“所有资源翻倍”：

```xml
<property>
  <name>yarn.scheduler.capacity.root.adhoc.maximum-am-resource-percent</name>
  <value>0.2</value>
</property>
```

修改后由有权限的管理员刷新队列：

```bash
yarn rmadmin -refreshQueues
yarn queue -status adhoc
yarn application -status application_1790294400000_0042
```

`rmadmin` 调用资源管理器管理功能；`-refreshQueues` 重新读取支持刷新的队列配置，不需要为了这个改动直接重启整个集群。HA 场景同步两台 RM 的配置，再按运维流程刷新并检查生效。修改容量不会凭空造出机器，也不保证即时回收既有容器；真实集群全满时，还要等释放资源或扩容。[队列参数与刷新依据](https://hadoop.apache.org/docs/r3.3.6/hadoop-yarn/hadoop-yarn-site/CapacityScheduler.html)

**第三步，核对提交参数，避免申请过大。** 以下是另一个已存在 Python 作业的完整提交形式，供理解参数；本例原任务已排队时不要再重复执行：

```bash
spark-submit \
  --master yarn \
  --deploy-mode cluster \
  --queue adhoc \
  --driver-memory 1g \
  --executor-memory 2g \
  --executor-cores 1 \
  --num-executors 2 \
  --conf spark.dynamicAllocation.enabled=false \
  /opt/jobs/daily_count.py
```

`--master yarn` 交给 YARN 调度；`--deploy-mode cluster` 把 Driver 放在集群；`--queue` 选队列；`--driver-memory`/`--executor-memory` 指各自 JVM 堆内存；`--executor-cores` 指每个 Executor 的核数；`--num-executors` 为固定 Executor 数；`--conf ...=false` 关闭动态分配以便演示固定数量。反斜杠是 Bash 换行续写，最后一项是已经存在的作业路径。

⭐ 容器实际资源还包含内存额外开销，并按 YARN 粒度取整，不能只加这几个堆内存数。cluster 模式 AM/Driver 内存看 Driver 参数；client 模式 AM 内存才主要看 `spark.yarn.am.memory`，不要混着调。[Spark on YARN](https://spark.apache.org/docs/3.5.7/running-on-yarn.html)

验收顺序：队列新值生效 → 原应用从 ACCEPTED 进入 RUNNING → Driver、Executor 正常 → 任务完成且输出符合预期。这里只定义验收标准，不声称已经实测。

### 5. 预防措施

- ⭐ 对等待时长、队列占用、AM 占用、用户额度和异常节点做监控。
- 为定时批任务安排错峰，并按业务重要性划分队列和提交权限。
- 提交前校验资源规格；为历史运行数据建立合理基线，避免一律给大内存。
- 固化队列配置变更、回退和检查流程；长期高负载再做容量规划。

## 🔥 面试口语版（200—300 字，可直接背）

> 我整理过一个任务排队的纸面案例，没有把它当成实际生产经历。现象是提交后一直停在已接受状态，还没真正运行。我会先看资源管理器页面里的应用诊断，再看队列容量、主控进程额度和节点剩余资源。案例里集群还有空闲，但临时队列已经达到最大容量，所以应用管家拿不到容器。我会先协调错峰，确有需要再调整队列份额和上限，核对兄弟队列份额总和，然后刷新配置。若诊断显示是主控进程额度不足，就单独处理那个限制，不能乱加执行器。最后确认任务进入运行状态、执行器起来、结果正常，再补等待时长告警和资源申请规范。

**背诵线索：未开工 → 看诊断 → 分清集群与队列 → 有依据地改限制 → 验证。**

## 版本与来源

核对日期：2026-09-25；Hadoop 3.3.6 的百分比容量模式、Spark 3.5.7。厂商 UI 和调度器版本可能不同，示例不表示所有企业都使用相同队列策略。

- [Capacity Scheduler](https://hadoop.apache.org/docs/r3.3.6/hadoop-yarn/hadoop-yarn-site/CapacityScheduler.html)：容量、最大容量、AM 比例和队列刷新。
- [YARN 命令](https://hadoop.apache.org/docs/r3.3.6/hadoop-yarn/hadoop-yarn-site/YarnCommands.html)：应用、队列和节点诊断。
- [Spark 3.5.7 on YARN](https://spark.apache.org/docs/3.5.7/running-on-yarn.html)：提交方式、Driver/AM 及额外内存。
