# Travel Planner (CrewAI)

一个最小可运行的多 Agent 旅游攻略 CLI。内置本地工具与 3 个 Agent（研究员/规划师/审稿人），支持命令行交互与详细日志输出。

## 环境准备

1) 创建与激活虚拟环境
```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate  # Windows
```

2) 安装依赖
```bash
pip install -r requirements.txt
```

3) 配置 LLM Key（真实模型调用，使用项目 .env）

- 在项目根目录创建或编辑 `.env`：
  ```bash
  OPENAI_API_KEY=sk-xxxx
  # 可选全局模型（LiteLLM 格式：<provider>/<model>）
  CREWAI_MODEL=openai/gpt-4o-mini
  # 可选分角色模型（优先级高于 CREWAI_MODEL）
  # RESEARCHER_MODEL=openai/gpt-4o-mini
  # PLANNER_MODEL=openai/gpt-4o-mini
  # REVIEWER_MODEL=openai/gpt-4o-mini
  # 可选：关闭遥测
  CREWAI_TELEMETRY_OPT_OUT=1
  ```

- 程序与 `restart.sh` 会自动加载 `.env`，无需依赖 `~/.zshrc`。

## 快速使用

交互模式（推荐）
```bash
python main.py
```

仅运行一次
```bash
python main.py --once --destination 东京 --days 3 --budget 适中 --preferences "美食, 博物馆"
```

指定日志文件（默认 `logs/travel.log`）
```bash
python main.py --log-file logs/travel.log
```

切换模型（覆盖环境变量 CREWAI_MODEL）
```bash
python main.py --model openai/gpt-4o-mini
```

分角色切换模型（优先级高于 CREWAI_MODEL）
```bash
python main.py \
  --researcher-model openai/gpt-4o-mini \
  --planner-model openai/gpt-4o-mini \
  --reviewer-model openai/gpt-4o-mini
```

## 重启脚本（包含环境变量）

使用项目根目录的 `restart.sh` 统一设置并启动：

```bash
./restart.sh --destination 东京 --days 3 --budget 适中 --preferences "美食, 博物馆"
```

说明：
- 脚本会尝试读取 `~/.zshrc`（以获取如 `OPENAI_API_KEY` 的密钥），并激活本地 `venv`。
- 在脚本内可直接配置启动所需变量：
  - `CREWAI_MODEL`（默认 `openai/gpt-4o-mini`）
  - 可选按角色覆盖：`RESEARCHER_MODEL`、`PLANNER_MODEL`、`REVIEWER_MODEL`
  - `CREWAI_TELEMETRY_OPT_OUT=1`（默认关闭遥测）
  - `TRAVEL_LOG_FILE`（默认 `logs/travel.log`）
- 所有传给 `restart.sh` 的参数会透传给 `main.py`。

## 命令行参数

- `--destination`: 目的地（如：东京/大阪/巴黎）。
- `--days`: 行程天数（整数）。
- `--budget`: 预算偏好（如：节省/适中/宽松 或 金额区间）。
- `--preferences`: 偏好标签，逗号分隔（如：`美食, 博物馆`）。
- `--log-file`: 日志文件路径（默认 `logs/travel.log`）。
- `--once`: 仅运行一次，不进入交互循环。
- `--model`: 覆盖默认模型（等价于环境变量 `CREWAI_MODEL`）。
- `--researcher-model`: 覆盖研究员模型（等价于 `RESEARCHER_MODEL`）。
- `--planner-model`: 覆盖规划师模型（等价于 `PLANNER_MODEL`）。
- `--reviewer-model`: 覆盖审稿人模型（等价于 `REVIEWER_MODEL`）。

## 环境变量

- `OPENAI_API_KEY`：真实模型调用所需（或按照 LiteLLM 对接的其他厂商变量）。
- `CREWAI_MODEL`：全局模型，示例：`openai/gpt-4o-mini`。
- `RESEARCHER_MODEL`、`PLANNER_MODEL`、`REVIEWER_MODEL`：按 Agent 细分的模型配置（优先级高于 `CREWAI_MODEL`）。
- `CREWAI_TELEMETRY_OPT_OUT=1`：可选，关闭遥测。
- `LOCAL_SEARCH_BASE_URL`：本地搜索服务地址，默认 `http://localhost:10004/search`（工具会以 `?q=...&format=json` 调用）。

建议把上述变量写入 `~/.zshrc`，例如：
```bash
export OPENAI_API_KEY=sk-xxxx
export CREWAI_MODEL=openai/gpt-4o-mini
# 可选分角色：
# export RESEARCHER_MODEL=openai/gpt-4o-mini
# export PLANNER_MODEL=openai/gpt-4o-mini
# export REVIEWER_MODEL=openai/gpt-4o-mini
```
保存后执行 `source ~/.zshrc` 使其生效。

## 日志

- 终端会显示详细的执行与对话日志（`verbose=True`）。
- 同步写入 `logs/travel.log`，便于回放与排查。

## 功能说明

- 多 Agent 顺序流水线（真实 LLM 调用）：
  - 旅行研究员：使用本地城市信息工具，给出城市画像、核心片区与预约/通勤要点。
  - 旅行研究员：新增“本地搜索”工具（调用 `LOCAL_SEARCH_BASE_URL`，默认 `http://localhost:10004/search`），用于实时信息（如天气/活动/闭馆提醒等）。
  - 行程规划师：按天（上午/下午/晚上）输出可执行行程表，控制密度与预算。
  - 审稿人：审查可行性与风险，给出改进版最终行程，可基于“修改请求”微调。
- 日志：
  - 运行时 `verbose=True` 打印详细对话与工具调用过程。
  - 主程序启用了 stdout “tee”，会将终端输出同时写入到日志文件。

提示：`.env` 中的 `CREWAI_TELEMETRY_OPT_OUT=1` 可关闭遥测。

### 本地搜索服务自检

先用 curl 检查你的服务：
```bash
curl -s "http://localhost:10004/search?q=深圳今天天气&format=json" | head
```
若返回 JSON，CLI 中研究员会自动调用“本地搜索”工具，并将结果要点出现在日志中（带有 `[search:query]` / `[search:raw]` 标记）。

## 主要文件

```
.
├── main.py             # CLI 入口（交互/一次性运行、tee 日志）
├── travel_agents.py    # Agents/Tasks/Crew 定义 + 本地工具
├── requirements.txt    # 依赖
└── README.md           # 说明
```

## 常见问题

- 日志看不到 Agent 细节？确认已在终端看到 `⏳ 正在生成行程...（已开启详细日志）`，Crew/Agent/Task 默认为 `verbose=True`。日志同时写入 `logs/travel.log`。
- 想扩展功能？在 `travel_agents.py` 中新增工具或 Agent，并在 `build_crew()` 中接入；也可替换为 `crewai-tools` 的网络工具（需配置 API Key）。
