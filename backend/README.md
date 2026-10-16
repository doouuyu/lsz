# 李时珍智能医师 · 后端 API

基于 FastAPI 的中医辨证辅助系统后端。架构：**LLM 存量知识 + 轻量 RAG 溯源 + 提示词工程**，不训练、不微调。

## 目录结构

```
backend/
├── app/
│   ├── main.py            # FastAPI 入口，启动时加载知识库，挂载 /api 与 /reports
│   ├── config.py          # 配置（多模型切换、RAG 权重等），读 .env
│   ├── models/
│   │   ├── knowledge.py    # 知识条目 / 图谱 数据模型
│   │   └── schemas.py      # API 请求/响应契约
│   ├── prompts/            # 辨证思维链 / 问诊 / 知识生成 系统提示词
│   ├── services/
│   │   ├── llm.py          # LLM 适配层（DeepSeek/Qwen/OpenAI，OpenAI 兼容）
│   │   ├── knowledge.py    # 知识库：加载 + 混合检索(BM25+语义) + 图谱构建
│   │   ├── diagnose.py     # 辨证编排：RAG → LLM → JSON 容错 → 回填出处
│   │   ├── session.py      # 会话存储（内存版，可换 Redis）
│   │   └── static_data.py  # 养生/慢病 静态预生成数据
│   └── api/                # 路由：chat / knowledge / regimen / chronic / report
├── data/                  # knowledge_base.json、养生/慢病数据、reports/
└── scripts/               # 知识库生成、epub 解析（模型相关，独立运行）
```

## 运行

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt           # 完整依赖
# 最小可运行集（无向量库/PDF）：
# pip install fastapi "uvicorn[standard]" openai pydantic-settings python-dotenv jieba rank-bm25

cp .env.example .env                       # 填入 DEEPSEEK_API_KEY，并按需改 HOST/PORT
python run.py                              # 读取 .env 的 HOST/PORT，绑定到局域网 192 IP
# 或显式指定：uvicorn app.main:app --reload --host 192.168.50.145 --port 8000
```

打开 http://192.168.50.145:8000/docs 查看交互式 API 文档（HOST/PORT 由 .env 控制）。

> Python 3.9+ 可运行。可选依赖（chromadb / sentence-transformers / weasyprint）缺失时服务自动降级，不影响启动。

## API 一览（前缀 `/api`）

| 接口 | 方法 | 说明 |
|---|---|---|
| `/chat/inquiry` | POST | 仿真问诊，判断四诊是否充分 |
| `/chat/diagnose` | POST | 辨证主流程，返回 8 步思维链 JSON + RAG 引证 |
| `/knowledge/search` | GET | 混合检索（BM25+语义），支持 category/disease/verified 过滤 |
| `/knowledge/graph` | GET | 知识图谱 nodes/links，可按病证过滤 |
| `/knowledge/entry/{id}` | GET | 单条详情（溯源弹窗） |
| `/knowledge/stats` | GET | 知识库统计 |
| `/regimen/seasonal` | GET | 四时养生（春/夏/秋/冬） |
| `/regimen/organ` | GET | 五脏调养（心/肝/脾/肺/肾） |
| `/chronic/diseases` | GET | 慢病病种 + 症状清单 |
| `/chronic/quick-diagnose` | POST | 慢病一键辨证（规则匹配，零成本） |
| `/report/generate` | POST | 生成诊疗报告（HTML，装 WeasyPrint 则出 PDF） |

### V2 多模态问诊（微信小程序 P0）

V2 使用匿名 `consultation_id` + `X-Consultation-Token`，业务调用均异步返回
`task_id`，通过 `/api/v2/tasks/{task_id}` 轮询。

| 接口 | 方法 | 说明 |
|---|---|---|
| `/v2/consultations` | POST | 创建并锁定报告视角 |
| `/v2/consultations/{id}/attachments` | POST/DELETE | 上传或删除统一医疗附件 |
| `/v2/consultations/{id}/prepare` | POST | 多模态初读并生成首问 |
| `/v2/consultations/{id}/answers` | POST | 提交一轮回答并生成下一问 |
| `/v2/consultations/{id}/finalize` | POST | 检索词、RAG 与最终八步报告 |
| `/v2/tasks/{task_id}` | GET | 查询异步任务 |
| `/v2/asr/realtime` | WebSocket | Fun-ASR 音频流代理（MP3/16kHz/单声道） |

生成并审查热词：

```bash
python scripts/build_asr_hotwords.py
python scripts/build_asr_hotwords.py --sync
```

首次 `--sync` 输出 `vocabulary_id`，写入 `ASR_VOCABULARY_ID` 后重启；已有 ID
时脚本执行完全更新。热词同步失败不会影响手动输入和后端启动。

Mock 测试与真实接口冒烟：

```bash
PYTHONPATH=. python -m pytest tests -q
python scripts/smoke_v2_bailian.py --attachment /path/to/deidentified.jpg
```

真实冒烟不进入普通 CI。部署必须保持单 worker，并在微信公众平台同时配置
HTTPS request/uploadFile 合法域名和 WSS socket 合法域名。

`/health` 返回知识库加载状态与检索引擎可用性。

## 设计要点

- **优雅降级**：jieba/rank_bm25 缺失 → 退化为字符级匹配；LLM 不可用 → 返回结构一致的兜底 JSON；WeasyPrint 缺失 → 报告回退 HTML。服务始终可启动。
- **RAG 引证**：仅 `verified=true` 条目进入引证源（溯源真实性），`step4` 出处按 `entry_id` 回填知识库真实卷次。
- **静态优先**：养生、慢病为预生成静态内容，不实时调模型，省成本提速（开发文档提醒①）。
- **升级接口**：`KnowledgeService._semantic_scores` 预留替换为 Chroma + embedding 向量检索。

## 知识库生成（模型相关，独立流程）

```bash
python3 scripts/generate_kb.py --resume     # 断点续生成至 2000 条
python3 scripts/generate_kb.py --dry-run     # 查看配额计划
```

> 后端服务每次启动从 `data/knowledge_base.json` 全量载入；生成进行中不影响已启动服务，重启即可加载新条目。
