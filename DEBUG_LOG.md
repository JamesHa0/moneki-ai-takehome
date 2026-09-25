# DEBUG_LOG

按 `docs/ASSIGNMENT.md` 第二关的要求，每个缺陷一条，六栏格式：

| 栏    | 写什么                   |
| ---- | --------------------- |
| 现象   | 怎么注意到的（哪道题、哪个输出、哪条日志） |
| 假设   | 当时的猜测，**包括猜错后排除掉的**   |
| 验证   | 做了什么实验来证实或排除，贴关键输出    |
| 根因   | 具体到文件和行               |
| 修复   | 对应的 commit            |
| 回归测试 | 测试名，以及它在修复前确实是红的证据    |

前两栏是调试叙事，后四栏是可核查的事实。**先复现，再猜，每一步都有命令和输出**——  
按 README 的说法，这一项看的正是过程，不是"修得快"。

## 条目索引

| #  | 缺陷                    | 层级  | 修复 commit                               |
| -- | --------------------- | --- | --------------------------------------- |
| 1  | 重建命令读回陈旧缓存，索引永不随知识库更新 | 索引层 | `c7ac40c` `5a0ef94` `63a77a1` `4af7396` |
| 2  | 清洗层未执行规范化、六条剔除和七字段去重  | 口径层 | `52a74e1` `36dd8ac`                     |
| 3+ | 见文末「待补条目」             |     |                                         |

---

## 1. 重建命令读回陈旧缓存，索引永不随知识库更新

**层级**：索引层 · `starter/kbqa/index.py` + `starter/kbqa/rebuild.py`

**影响面**：契约 §8 规定评审会替换 `data/` 与 `knowledge_base/` 两个目录，然后执行重建命令。  
缓存键与知识库内容无关 ⇒ 换库之后索引一动不动，隐藏题库整体失效。  
属于"本地看着正常、交上去就失效"的一类，也是本单最值得先修的原因。

### 现象

刚拿到项目的时候进行了重建，第二天又重建（间隔12小时）发现`starter/var/clean.db`的mtime变了，而`starter/.cache/index.json`的mtime没变。

查看打印输出后再次重建发现打印的是旧缓存的计数。

### 假设

四条猜测，前三条都被排除，最后一条才站住：

1. **猜「重建命令没跑成功，我看到的是上次留下的产物」**     
   → 排除。关键输出齐全（`清洗完成` / `索引完成` / `产物`），没有异常、没有回退。     
   但顺手发现一个可疑点：全程只花了 **0.2 秒**。即使不考虑索引，清洗 18628 行也不应该这么快，     
   0.2 秒不合理 —— 有东西被跳过了。
2. **猜「知识库目录配置指错了，重建读的是另一个目录」**     
   → 排除。输出第一行打印的就是知识库目录的绝对路径（`D:` 盘符 + `moneki/knowledge_base`），与预期一致；     
   而且目录指错的结果应该是 **0 篇文档**，不会是 25 篇。
3. **猜「索引构建抛了异常被吞掉，所以旧缓存文件被留了下来」**     
   → 排除。`索引完成：25 篇文档，53 个片段` 是正常打印出来的，没有告警、没有 traceback；     
   读 `rebuild.py` 全文，也没有任何 `try/except` 会吞掉重建异常。
4. **最后读代码，才发现是两处独立的原因叠在一起**：     
   `load_index(kb_dir, path, rebuild=False)` 的 `rebuild` 默认取 `False`，见缓存键匹配就直接返回缓存；     
   而 `content_key()` 只哈希三个版本号、与知识库内容无关，所以这个键**永远**匹配得上。     
   两处缺一不可 —— 只要键能对上，重建命令就永远只是把缓存读了一遍。

### 验证

**实验 1 · 复现「只有索引不动」**

```bash
$ ls -la --time-style=+"%m-%d %H:%M" starter/var/clean.db starter/.cache/index.json
09-25 07:58  starter/var/clean.db        # 上一条重建命令刚重写过
09-24 19:46  starter/.cache/index.json   # 还是 12 小时前那次留下的
```

两次重建之间还重启过一次服务，缓存依然不动 —— 排除「偶然」。

**实验 2 · 耗时只能作线索，决定性的证据是构建数量**

同一条命令、同一台机器：

```bash
# 修复前
产物：...\starter\var\clean.db、...\starter\.cache\index.json（0.2 秒）

# 修复后
索引完成：32 篇文档，80 个片段
产物：...\starter\var\clean.db、...\starter\.cache\index.json
```

耗时受磁盘缓存环境影响，不能单独作为结论；修复前后输出中的文档数和片段数变化才是硬证据。

**实验 3 · 按当前代码重建，应该得到多少**

```bash
$ uv run python -c "import sys;sys.path.insert(0,'.');from pathlib import Path;from kbqa.index import build_index;i=build_index(Path('../knowledge_base'));print(len(i.docs_meta),'篇文档,',len(i.chunks),'个片段')"
32 篇文档, 80 个片段
```

缓存里是 25 / 53 —— 与代码应得的不同，排除「缓存的数字就是对的」。

**实验 4 · 三个测试，确认修复前确实是红的**

```bash
$ uv run python -m pytest tests/test_rebuild.py -q
3 failed
FAILED tests/test_rebuild.py::test_content_key_tracks_knowledge_base_content
FAILED tests/test_rebuild.py::test_content_key_tracks_existing_document_changes
FAILED tests/test_rebuild.py::test_rebuild_command_forces_index_rebuild
```

**实验 5 · 分开修，看红灯是否精确移动**

这条用来证明两处是**独立**原因，而不是改一处就够：

```bash
# 只修 content_key 之后
$ uv run python -m pytest tests/test_rebuild.py -q
2 passed, 1 failed      # 剩下那条正是 test_rebuild_command_forces_index_rebuild

# 再修 rebuild.py 之后
$ uv run python -m pytest tests -q
25 passed               # 全套；只修 content_key 时是 24 passed, 1 failed
```

**实验 6 · 反证：修好之后「重建」是真重建**

```bash
$ uv run python -m kbqa.rebuild && ls -la --time-style=+"%H:%M:%S" .cache/index.json
14:53:55
$ uv run python -m kbqa.rebuild && ls -la --time-style=+"%H:%M:%S" .cache/index.json
14:54:00
```

缓存的 mtime 每次都变 —— 修复前第二次根本不会写文件。

**实验 7 · 确认强制重算不会引入抖动**

```bash
$ sha256sum .cache/index.json && uv run python -m kbqa.rebuild >/dev/null && sha256sum .cache/index.json
695dfb9bd5754e58bed9a15c31809902fb97039000c8d947404dd63d81435870  .cache/index.json
695dfb9bd5754e58bed9a15c31809902fb97039000c8d947404dd63d81435870  .cache/index.json
```

两次一致 ⇒ 索引构建是确定性的。绝对耗时随磁盘缓存和运行环境影响，`rebuild=True` 的关键代价是每次真实重算，而不是让索引内容抖动。

### 根因

**两处独立的原因叠在一起，缺一不可。**

| 位置                                         | 问题                                                                                                                                              |
| ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `starter/kbqa/index.py:23` `content_key()` | 只把 `INDEX_VERSION` / `CHUNKER_VERSION` / `TOKENIZER_VERSION` 拼起来哈希，**与知识库内容无关**。换库、加文档、改文档都不会让缓存失效。                                             |
| `starter/kbqa/rebuild.py:22`               | 调 `load_index(settings.kb_dir, settings.index_path)`，`rebuild` 参数取默认值 `False`。`load_index` 见缓存键匹配就把缓存文件原样返回——「重建」命令实际上只是读了一遍缓存，并把旧的文档/片段计数打印出来。 |

两处都修的理由是不同的：

- `content_key` 管「**内容变了要失效**」——换库、加文档、改文档；
- `rebuild=True` 管「**内容没变也强制重算**」——缓存文件被改坏、构建逻辑变了但版本号忘了加这一类。

只修 `content_key` 时，第三个测试仍然红；红灯精确地停在 `rebuild.py` 那一行。

### 修复

| commit    | 类型             | 内容                                                                                      |
| --------- | -------------- | --------------------------------------------------------------------------------------- |
| `c7ac40c` | `test(index)`  | 三个会红的测试。第二个用例是刻意加的"防半修"：同一路径**原地改写正文**也必须让键变（两个样本正文等长 5 个字，所以"只哈希文件大小"的写法同样过不了）         |
| `5a0ef94` | `fix(index)`   | `content_key` 纳入每个文件的**相对路径 + 原始内容**；路径与内容之间用 `\0` 分隔避免拼接歧义；按路径排序保证键稳定；`kb_dir` 不存在时不报错 |
| `63a77a1` | `fix(rebuild)` | 显式传 `rebuild=True`；同时删掉原来那句错误注释（"缓存还有效就不用重算，省几秒"——它本身就是这个缺陷的辩护词）                        |
| `4af7396` | `chore(index)` | 刷新索引缓存：键 `8651fac326e2 → 425e62cc8a3d`，文档 `25 → 32`，片段 `53 → 80`                        |

### 回归测试

文件：`starter/tests/test_rebuild.py`  
修复前 `3 failed`（输出见「验证」栏），修复后 `3 passed`。

| 测试                                                  | 锁住什么                                                                                                   | 修复前    | 修复后    |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | ------ | ------ |
| `test_content_key_tracks_knowledge_base_content`    | 知识库新增一篇 → 缓存键必须变                                                                                       | FAILED | PASSED |
| `test_content_key_tracks_existing_document_changes` | 同一路径原地改正文 → 缓存键必须变（防"只哈希路径"的半修）                                                                        | FAILED | PASSED |
| `test_rebuild_command_forces_index_rebuild`         | 重建命令必须传 `rebuild=True`（monkeypatch 替掉 `load_settings`/`build_clean_db`/`load_index`，全程在 `tmp_path` 里跑） | FAILED | PASSED |

全套：`cd starter && uv run python -m pytest tests -q`

- 测试刚加入时：`22 passed, 3 failed`
- 只修 `content_key()` 后：`24 passed, 1 failed`
- 再修 `rebuild=True` 后：**`25 passed`**

---

## 2. 清洗层未执行规范化、六条剔除和七字段去重

**层级**：口径层 · `starter/kbqa/cleaning.py`

**影响面**：`metrics` 接口所有数字都建立在 `sales_clean` 上。清洗没有执行时，脏日期仍在表里、门店和商品写法没有统一，退款与合法多行订单的边界也不可靠，指标即使 SQL 写对也得不到正确结果。

### 现象

第一次跑公开题库时，`metrics` 分类几乎全红，`/api/health` 返回的 `valid_sales_rows` 是 18628，和评测期望的 18290 对不上。继续查看 `cleaning_report`，六项剔除计数全部为 0；再直接查 `sales_clean`，能看到 `2026/5/3` 这样的日期和小写、带空格的门店编号仍然原样保留。

### 假设

1. **猜「是 `tools.py` 的汇总 SQL 算错了」**  
   → 先排除。`metrics` 的差异确实存在，但 `cleaning_report` 全部为 0 说明问题发生在更前面的清洗阶段；如果清洗没产生有效明细，后面再怎么改聚合 SQL 也只能把错误数据算得更整齐。
2. **猜「是测试数据或评测期望写错了」**  
   → 排除。用迷你数据写清洗红测试后，当前实现仍然原样保留非法日期、规范化和去重都没有发生，说明是 `clean_rows()` 没实现，而不是题库问题。
3. **最后核对代码和输出**：`clean_rows()` 只是把原始行搬进 `sales_clean`，没有调用任何日期解析、字段规范化或去重逻辑。

### 验证

**实验 1 · 先写会红的清洗测试**

```bash
$ uv run python -m pytest tests/test_cleaning.py -q
4 failed, 1 passed
```

失败分别覆盖：六项剔除计数、清洗后的日期/外键/唯一性不变式、可恢复脏写法的规范化和七字段去重。

**实验 2 · 修复前直接看真实数据**

```text
raw_rows: 18628
removed: 8/150/30/10/40/100 全为 0
kept_rows: 18628
valid_sales_rows: 18628
```

`sales_clean` 中仍存在 `2026/5/3`，证明日期没有统一成 ISO 格式。

**实验 3 · 修复后核对随包数据**

```text
raw_rows: 18628
1_unparseable_date: 8
2_empty_amount: 150
3_qty_le_zero: 30
4_store_not_in_stores: 10
5_product_not_in_products: 40
6_duplicate_row: 100
kept_rows: 18290
kept_sales_rows: 18196
kept_refund_rows: 94
```

六项剔除计数之和为 338，满足 `raw_rows - kept_rows == 338`。

**实验 4 · 日期方向自检**

```python
parse_date("25-06-2026") == "2026-06-25"
parse_date("2026/5/3") == "2026-05-03"
parse_date("2026-02-30") is None
```

第三条用于证明不是只做正则匹配，而是用 `datetime.date()` 做了真实日历校验。

### 根因

| 位置 | 问题 |
| --- | --- |
| `56f7a1f:starter/kbqa/cleaning.py:77` `clean_rows()` | 原实现把 `sales` 原样搬进 `sales_clean`，没有执行任何规范化或剔除，`CleaningReport.removed` 因此永远全为 0。 |
| `56f7a1f:starter/kbqa/cleaning.py:77` `clean_rows()` | 缺失日期解析，`YYYY/M/D`、`DD-MM-YYYY` 没有统一为 ISO，非法日期也没有经过 `date()` 校验。 |
| `56f7a1f:starter/kbqa/cleaning.py:77` `clean_rows()` | 缺失七字段去重；同时没有先规范化 `store_id` / `product_id`，所以既可能漏掉重复行，也可能把可恢复写法误判成脏外键。 |

### 修复

| commit | 类型 | 内容 |
| --- | --- | --- |
| `52a74e1` | `test(clean)` | 新增基于迷你数据的红测试，覆盖日期格式、真实日期校验、六项剔除、外键顺序、合法多行订单和七字段去重。 |
| `36dd8ac` | `fix(clean)` | 新增 `parse_date()`，连字符格式也接受不补零写法；按规范化和六步剔除顺序重写 `clean_rows()`；金额以整数分保存；最后按规范化后的七字段去重；销售行与退款行按金额正负分别统计。 |

### 回归测试

文件：`starter/tests/test_cleaning.py`

| 测试 | 锁住什么 | 修复前 | 修复后 |
| --- | --- | --- | --- |
| `test_removal_counts` | 六项剔除顺序与计数；`raw_rows - kept_rows == removed 之和` | FAILED | PASSED |
| `test_cleaned_table_invariants` | 日期均为 ISO、外键均有效、七字段无重复 | FAILED | PASSED |
| `test_recoverable_dirty_values_are_normalised_not_dropped` | 先规范化再判外键；`YYYY/M/D`、`DD-MM-YYYY`、金额符号正确处理 | FAILED | PASSED |
| `test_multiline_order_and_refund_survive` | 同单不同商品、同单同商品但支付方式不同、退款行均保留 | PASSED | PASSED |
| `test_duplicate_is_compared_after_normalisation` | 规范化后七字段相同的行只保留一条 | FAILED | PASSED |

全套：`cd starter && uv run python -m pytest tests -q`

- 清洗测试刚加入时：`18 passed, 4 failed`
- 清洗实现完成后：`22 passed`

---

## 待补条目（已知缺陷，尚未成条）

| 层级  | 位置                                         | 缺陷                                                                                                      | 状态                                |
| --- | ------------------------------------------ | ------------------------------------------------------------------------------------------------------- | --------------------------------- |
| 口径层 | `tools.py:52` `_where()`                   | 日期用开区间 `date < end`（`clause = ["date >= ?", "date < ?"]`），闭区间的最后一天被漏掉（M06：应返回 998.00 / 27 单，实得 0）       | 待修                                |
| 口径层 | `tools.py:93` `query_metrics()`            | `is_refund=0` 把退款排除在净营业额之外、`refund_amount` 硬编码 0、`orders` 用 `COUNT(*)` 而非去重 `order_id`                  | 待修                                |
| 索引层 | `loader.py:12`                             | `SUPPORTED_SUFFIXES = {".md", ".markdown"}`，`.txt`/`.html` 全被跳过 → KB-022 / KB-061 / KB-062 三份金标文档根本没进索引 | 待修                                |
| 索引层 | `loader.py:82`                             | 只按 UTF-8 + `errors="ignore"` 解码，KB-062 实为 GBK 会静默乱码                                                     | 待修                                |
| 索引层 | `chunker.py:41`                            | `range(0, len(text) - CHUNK_SIZE, ...)` 丢掉最后一块                                                          | 待修                                |
| 索引层 | `tokenizer.py:22`                          | 中文只 `split()` → 纯中文问句退化成 1 个 token，BM25 完全失效                                                            | 待修                                |
| 检索层 | `retriever.py:307`                         | 先取满 top-k 再按 `excluded` 过滤 → 结果可能不足 5 条                                                                 | 待修                                |
| 检索层 | `retriever.py:276`                         | `hit.doc_id = ordered[len(hits)].doc_id` 把 doc_id 换成另一篇文档 → 引用逐字校验必红                                    | 待修                                |
| 服务层 | `service.py:70`                            | `kb_docs` 数目录文件数（36）而非入库文档数（应为 35）                                                                      | 待修                                |
| 安全  | `tools.py:74` `run_sql()`                  | 任意 SQL + `commit()`，连接无 `mode=ro` → `DROP TABLE` 真能生效，违反"数据库不能有任何改动"                                    | 待修                                |
| 编排层 | `answerer.py:28` `MAX_CONTEXT_CHARS = 200` | 引文被截到 200 字（第 129 行用到），逐字校验可能因截断而变红                                                                     | 待修                                |

---
