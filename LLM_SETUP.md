# LLM 接入说明

## 1. 用了什么

- 厂商：DeepSeek
- 模型：`deepseek-flash`
- 协议：OpenAI 兼容 Chat Completions
- 调用方式：Python 标准 HTTP 客户端 `httpx` 0.28.1
- 服务只调用：

```text
POST {LLM_BASE_URL}/chat/completions
```

`LLM_BASE_URL` 原样使用，不自动补 `/v1`，不截掉路径前缀。

## 2. 配置从哪里读

配置只从服务进程的环境变量读取，不读取 `.env`：

| 变量 | 含义 | 默认值 |
| --- | --- | --- |
| `LLM_BASE_URL` | 模型服务地址 | 空 |
| `LLM_API_KEY` | 模型 Key | 空 |
| `LLM_MODEL` | 模型名 | 空 |
| `LLM_TIMEOUT` | 单次模型调用超时秒数 | `120` |
| `CHAT_BUDGET` | `/api/chat` 总预算秒数 | `150` |

三项 LLM 配置全部非空时进入 `live`，否则进入 `mock` 降级模式。

## 3. 怎么换成你们的

评审的标准接入方式仍然是把配置放进**服务进程环境变量**；本服务不会主动读取 `.env`。
`starter/.env.example` 只是可选的“抄文件填空”模板，环境变量路线优先。

1. 在启动服务的同一个终端设置：

```powershell
$env:LLM_BASE_URL = "https://api.deepseek.com"
$env:LLM_API_KEY = "sk-你的Key"
$env:LLM_MODEL = "deepseek-flash"
```

2. 在同一个终端重启服务：

```powershell
cd starter
uv run python -m uvicorn kbqa.server:app --host 127.0.0.1 --port 8000
```

3. 确认 live 模式：

```bash
curl -s http://127.0.0.1:8000/api/health | python -c "import json,sys; print(json.load(sys.stdin)['llm_mode'])"
```

期望输出：

```text
live
```

环境变量在进程启动时读取，修改后必须重启服务。模型配置与索引无关，不需要重建索引。

### 可选：用 `uv` 显式加载 `.env`

这不是默认启动方式，也不会改变服务只读环境变量的行为。`uv` 会把文件内容注入子进程环境，
因此 `make run` 仍然不会自动加载 `.env`。

```powershell
cd starter
Copy-Item .env.example .env
# 编辑 .env，填入 LLM_API_KEY
uv run --env-file .env python -m uvicorn kbqa.server:app --host 127.0.0.1 --port 8000
```

如果评审已经设置了同名环境变量，应直接使用环境变量路线，不要用 `.env` 覆盖评审配置。

## 4. 怎么看到发给模型的请求

启动代理：

```bash
cd starter
uv run python ../eval/llm_gateway.py proxy \
  --upstream https://api.deepseek.com \
  --port 8021 \
  --log ../notes/llm_traffic.jsonl
```

用代理打印的地址作为服务环境变量：

```text
LLM_BASE_URL=http://127.0.0.1:8021/ds-gw
```

每次模型请求和响应都会写入 `notes/llm_traffic.jsonl`。代理不记录 Authorization 的值，只记录长度。

脱敏样例：

```json
{
  "method": "POST",
  "path": "/ds-gw/chat/completions",
  "upstream_url": "https://api.deepseek.com/chat/completions",
  "response_status": 200,
  "authorization_length": 42,
  "request_body": {
    "model": "deepseek-flash",
    "messages": [
      {"role": "system", "content": "..."},
      {"role": "user", "content": "..."}
    ],
    "tools": [
      {"type": "function", "function": {"name": "query_metrics"}}
    ],
    "tool_choice": "auto",
    "max_tokens": 4096
  },
  "usage": {
    "prompt_tokens": 1848,
    "completion_tokens": 99,
    "total_tokens": 1947
  }
}
```

日志中保留完整提示词、每轮消息、工具定义、模型响应和用量。

## 5. 没有 Key 时会怎样

服务照常启动，四个接口的返回：

| 接口 | 无 Key（`llm_mode=mock`）时 |
|---|---|
| `/api/health` | HTTP 200，`llm_mode: "mock"`，其余健康字段照常 |
| `/api/metrics/summary`、`/api/metrics/daily` | HTTP 200，正常指标数据（不经过模型） |
| `/api/retrieve` | HTTP 200，正常检索结果（不经过模型） |
| `/api/chat` | HTTP 200，`answer_type` 为 `data` / `doc` / `hybrid` / `refusal` 之一，正文由本地模板从工具结果渲染，**不会因缺 Key 返回 HTTP 500** |

降级策略：不使用任何模型能力，改为确定性模板回答；数字与引用同样来自工具与检索结果。
- 无 Key / 未配置 Key 时，公开题库读数为 **95.00 / 100**（降级模式，`c47da83`）；
  配置 Key 后的真实模型读数为 **97.00 / 100**（见第 7 节与 `EVAL_REPORT.md`）。
  仓库根目录的 `report.md` 是 2026-09-24 的起跑线快照（17.00 / 100），不是当前水位。

## 6. 依赖与安装

- 无额外模型 SDK，无需下载模型文件。
- 已有依赖：`fastapi`、`uvicorn`、`httpx`、`pytest`。
- 不需要 `python-dotenv`。
- 真实模型调用需要网络，单次 `/api/chat` 通常数秒到数十秒。
- **首次启动耗时**：本机实测 **约 3 秒**（启动到 `/api/health` 可返回，Windows 11 + Python 3.12，
  无需下载模型文件、无需重建索引）。首次运行 `make rebuild` 会生成 `clean.db` 与检索索引，
  耗时取决于数据量，本机约十几秒。

## 7. 自测结果

### OpenAI 兼容预检

执行命令：

```bash
cd starter
uv run python ../eval/llm_gateway.py preflight \
  --service-url http://127.0.0.1:8015 \
  --out ../notes/preflight
```

预检结果：

| 检查 | 结果 |
| --- | --- |
| P1 `LLM_BASE_URL` 原样使用 | 通过 |
| P2 `LLM_MODEL` 未写死 | 通过 |
| P3 Bearer Key | 通过 |
| P4 参数白名单 | 通过 |
| P5 `max_tokens` | 通过 |
| P6 路径限制 | 通过 |
| P7 工具调用协议 | 通过 |
| P8 HTTP 200 + JSON | 通过 |
| P9 失败时结构化 refusal | 通过 |
| P10 思考内容不泄漏 | 通过 |
| P11 180 秒时限 | 通过 |
| P12 注入变量后 `llm_mode=live` | 通过 |
| P13 `reasoning_content` 原轮回传 | 通过 |
| P14 空行与 keep-alive | 通过 |

总体：**14 / 14 通过**。

完整报告见：

- `notes/preflight/preflight_report.md`
- `notes/preflight/preflight_report.json`

### 真实模型验收（本机，真实 Key）

使用 DeepSeek `deepseek-flash`，服务经本地代理调用真实官方接口后运行。
下面这条是**单类复测**的写法（`--only` 一次只接受一个值，跑多类要去掉该参数）：

```bash
python eval/run_eval.py \
  --base-url http://127.0.0.1:8015 \
  --questions eval/public_questions.jsonl \
  --only doc \
  --out notes/eval-live-doc
```

截至 2026-09-27 的最新结果（`c47da83`，全量 55 题）：

```text
总分：97.00 / 100        全绿：53 / 55        检查点 461 / 463

metrics       6 / 6          data         12 / 12
doc          14 / 16         version       6 / 6
hybrid       18 / 18         multi_turn    9 / 9
refusal       8 / 8          safety        9 / 9
retrieval    14 / 15         health        1 / 1
```

分阶段的 live 读数（同一份评测器、同一份数据，按运行时的 commit 归属）：

```text
接入首日（三个 live 缺陷未修）          8.00 / 16（doc）    dc66c37
模板回退约束 + 挑句排序修复后          10.00 ~ 12.00 / 16  d43cda6 ~ 96577ca
D1-06 收口 / 日期白名单后              14.00 / 16（六连跑） b288ad9
D1-09 数字预算 / year 降权 / 剥注入     91.00 / 100         f1f25e2
异常题路由 + 最好/最差排名后           **97.00 / 100**      c47da83
```

全量跑法（与上面 `--only doc` 同一条链路，去掉 `--only`）：

```bash
python eval/run_eval.py \
  --base-url http://127.0.0.1:8015 \
  --questions eval/public_questions.jsonl \
  --out notes/eval-live-full
```

这证明真实 Key、模型名、代理、工具调用与 `/api/chat` 链路已经完全连通；
C04 的模型请求数由 5 降到 3，C06/C07 不再受示例日期或工具循环影响。
剩余 2 项（`R04` 检索排序 1 分、`C02` 挑句 2 分）的逐项归因见 `EVAL_REPORT.md` §五。


## 8. 已知限制

- `.env` 不会自动加载；配置必须进入服务进程环境。
- 环境变量在启动时读取，修改后必须重启服务。
- 当前说明只覆盖 OpenAI 兼容 Chat Completions 路线。
- 真实模型下仍有 2 项未满分，共 3 分：`R04`（检索 top-5 缺 KB-022，1 分）、
  `C02`（挑句挑到 KB-040 的表格行却没带表头，导致「麸质/大豆/芝麻」未出现，2 分）。
  此前报告里提到的 `D03`/`D06`/`V01`/`H01`/`H06`/`S01` 与 `C04` 均已修复。
  逐项归因见 `EVAL_REPORT.md` §五。
- **同一批题的两次 live 读数有 ±2 的模型波动**（`C07` 在 `doc` 上 14↔16 的往复、
  `C02` 的 `cite_max` 时过时挂），单次读数不等于长期稳定值。
- `doc` 已全绿；完整 live 题库仍有 R04、D03、D06、V01、H01、H06、S01 未过。
  D03/D06 是模型额外调用过大的 `top_products` 结果触发证据数字上限；
  V01/S01 是模型额外引入旧版信息或文档干扰数字；H01/H06 是仍缺 hybrid 数字证据。
  逐项归因见 `EVAL_REPORT.md` §五。
