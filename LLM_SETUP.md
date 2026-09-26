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

- 服务可以正常启动。
- `/api/health` 返回 `llm_mode: "mock"`。
- `/api/metrics/*`、`/api/retrieve` 和知识库检索正常工作。
- `/api/chat` 进入本地模板回答或返回结构化结果，不会因缺少 Key 返回 HTTP 500。
- 无 Key 时公开题库读数为 49.00 / 100（降级模式，作为对照）；最终得分见 `EVAL_REPORT.md`。
  仓库根目录的 `report.md` 是 2026-09-24 的起跑线快照（17.00 / 100），不是当前水位。

## 6. 依赖与安装

- 无额外模型 SDK，无需下载模型文件。
- 已有依赖：`fastapi`、`uvicorn`、`httpx`、`pytest`。
- 不需要 `python-dotenv`。
- 真实模型调用需要网络，单次 `/api/chat` 通常数秒到数十秒。

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

### 真实模型小范围验收

使用 DeepSeek `deepseek-flash`，服务经本地代理调用真实官方接口后运行：

```bash
python eval/run_eval.py \
  --base-url http://127.0.0.1:8015 \
  --questions eval/public_questions.jsonl \
  --only doc \
  --out notes/eval-live-doc
```

截至 2026-09-26 的结果：

```text
doc：16.00 / 16.00
C01–C08 全部通过

完整公开题库：84.00 / 100（48 / 55 题全绿）
```

这证明真实 Key、模型名、代理、工具调用与 `/api/chat` 链路已经连通。D1-06 修复后，
C04 的模型请求数从 5 降到 3，C06/C07 不再受示例日期或工具循环影响。

## 8. 已知限制

- `.env` 不会自动加载；配置必须进入服务进程环境。
- 环境变量在启动时读取，修改后必须重启服务。
- 当前说明只覆盖 OpenAI 兼容 Chat Completions 路线。
- `doc` 已全绿；完整 live 题库仍有 R04、D03、D06、V01、H01、H06、S01 未过。
  D03/D06 是模型额外调用过大的 `top_products` 结果触发证据数字上限；
  V01/S01 是模型额外引入旧版信息或文档干扰数字；H01/H06 是仍缺 hybrid 数字证据。
  逐项归因见 `EVAL_REPORT.md` §五。
