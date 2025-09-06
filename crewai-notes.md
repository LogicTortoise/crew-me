# CrewAI 最新文档要点与多 Agent 构建范式（持续更新）

> 基于 docs.crewai.com、GitHub 主仓与 crewai-tools 的最新可访问内容整理（已抓取概念/API 页、工具 README、站点地图）。用于快速上手与方案选型。

## 版本与来源

- 文档主页：<https://docs.crewai.com>
- 核心概念：Agents / Tasks / Crews / Processes / Tools / Memory / Flows / Knowledge / Event Listeners / LLMs / CLI
- API 参考（云/控制面）：`POST /kickoff`、`GET /inputs`、`GET /status`（见文档 API Reference）
- GitHub（主仓）：<https://github.com/crewAIInc/crewAI>
- 工具生态：<https://github.com/crewAIInc/crewai-tools>

---

## 核心概念

- **Agent**：专家角色，包含“角色/目标/背景/工具”，可配置是否允许委派（allow_delegation）与详细日志（verbose）。
- **Task**：对 Agent 的一次清晰委托，包含描述、期望产出（expected_output）、分配的 Agent、可复用的上游输入。
- **Crew**：将多个 Agents 与 Tasks 以流程进行编排的执行器。
- **Process**：执行策略，常见为顺序（sequential）与层级（hierarchical，含管理者/返工回路）。
- **Flows**：事件驱动式编排，强调更细粒度控制与减少 LLM 调用；与 Crews 可互通。
- **Tools**：以装饰器 `@tool` 或继承 `BaseTool` 扩展，也可使用官方 `crewai-tools`。
- **Memory / Knowledge**：记忆与知识管理，将会话态与外部知识融入决策与产出。
- **LLMs**：为不同 Agent/步骤配置不同模型（本地/云端），可差异化温度、上下文长度等。

---

## 快速上手

```bash
pip install crewai
# 可选工具生态
pip install crewai-tools
```

最小骨架：定义 Tools → 定义 Agents（角色/目标/工具）→ 定义 Tasks（描述/验收/分配 Agent）→ `Crew(process=...)` 编排 → `crew.kickoff(inputs=...)` 执行。

- **全局输入**：通过 `kickoff(inputs={...})` 注入，贯穿任务链。
- **可观测性**：建议开启 `verbose`，并使用事件监听（Event Listeners）记录工具调用、任务状态与中间产物。

---

## 多 Agent 构建范式

- **顺序流水线（Sequential/Pipeline）**：
  - 线性分工（调研 → 写作 → 校对），简单稳定，易控成本与上下文。
  - 适用：明确流程、线性产出、对时延/成本敏感。

- **层级管理（Hierarchical/Manager-Workers）**：
  - 经理 Agent 进行任务拆解、指派、审阅与返工决策。
  - 适用：复杂/目标模糊/需质量门控与返工闭环。

- **互评协作（Peer Review/Collaboration）**：
  - A 产出 → B 评审 → A 修订，降低幻觉与事实错误。
  - 适用：高可信度/合规要求高的场景。

- **规划-执行（Planner-Executor）**：
  - 规划 Agent 生成子任务图，执行 Agents 逐步完成。
  - 适用：探索性、难以一步预定义流程的任务。

- **路由-专家池（Router-Specialist）**：
  - 路由 Agent 根据输入类型分发到对应专家。
  - 适用：多领域统一入口、多模态输入分流。

- **RAG/知识增强（Retriever-Specialists）**：
  - 检索 Agent 拉取知识库证据，专家基于证据产出。
  - 适用：知识密集型、需可溯源证据链。

- **Flows（事件驱动）**：
  - 对步骤/回调/事件进行精细控制，目标是以尽可能少的 LLM 调用完成精确编排；可与 Crews 结合。
  - 适用：需要强可控性、强一致性与低延迟的复杂编排。

---

## 工具生态（crewai-tools）

- 常用类目：
  - 文件：`FileReadTool`、`FileWriteTool`
  - 抓取：`ScrapeWebsiteTool`、`SeleniumScrapingTool`
  - 搜索/API：`SerperApiTool`、`EXASearchTool`
  - 数据库：`PGSearchTool`、`MySQLSearchTool`
  - 向量库：`MongoDBVectorSearchTool`、`QdrantVectorSearchTool`、`WeaviateVectorSearchTool`
  - AI 能力：`DallETool`、`VisionTool`、`StagehandTool`

- 自定义工具两种方式：
  - 装饰器：
    ```python
    from crewai import tool

    @tool("结构化摘要")
    def structured_summary(text: str) -> str:
        # 返回结构化要点
        return "- 结论: ...\n- 证据: ...\n- 风险: ..."
    ```
  - 继承 `BaseTool`：
    ```python
    from crewai.tools import BaseTool

    class MyTool(BaseTool):
        name: str = "MyTool"
        description: str = "Do something useful"

        def _run(self, *args, **kwargs):
            return "result"
    ```

- **MCP 支持**：`pip install crewai-tools[mcp]`，使用 `MCPServerAdapter` 将 MCP 服务器的工具 1:1 映射为 CrewAI Tools，支持 STDIO/SSE 两种连接方式。

---

## 事件与可观测性

- **Event Listeners**：监听任务开始/结束、工具调用、错误等事件，用于审计、Tracing 与指标。
- **CLI**：提供项目初始化、运行与调试（详见文档的 CLI 页面）。
- **Cloud/Enterprise**：控制平面、RBAC、工具/Agent 仓库、幻觉防护与集成生态；API 包含 `POST /kickoff`、`GET /inputs`、`GET /status` 等以供编排与状态追踪。

---

## 实践要点与最佳实践

- **任务切粒度**：每个 Task 只做“一件事”，在 `expected_output` 中明确结构、字数、验收标准。
- **角色清晰**：Agent 的“角色/目标/边界/风格”写清，降低风格漂移与误用工具。
- **工具最小授权**：仅将必要工具绑定到需要的 Agent；限制具有副作用（写文件/外网）的能力范围。
- **上下文控制**：控制 Token，分阶段摘要传递上下文；关键节点保留证据链与引用。
- **质量门控**：在关键环节加入 Reviewer/Fact-Checker；对返工回路设置轮次与放行阈值。
- **成本与性能**：优先顺序流程 + 关键节点审查；需要精细控制/更少 LLM 调用时采用 Flows。
- **可观测与回放**：启用 verbose、事件监听、保存中间产物，便于调试与复现。

---

## 何时选择哪种范式

- 明确流程/线性产出：优先顺序流水线。
- 目标模糊/需拆解与把关：层级管理。
- 可靠性优先/防幻觉：互评协作 + Reviewer/Fact-Checker。
- 知识密集/需证据链：RAG（检索 Agent + 专家 Agent）。
- 多入口/多领域分流：路由-专家池。
- 需要细粒度控制与低时延：Flows（事件驱动）或 Flows + Crews 结合。

---

## 最小可运行示例（顺序流水线）

```python
# pip install crewai crewai-tools
from crewai import Agent, Task, Crew, Process, tool

@tool("结构化摘要")
def structured_summary(text: str) -> str:
    """
    将文本归纳为要点: 结论/证据/风险。输入: text; 输出: markdown要点。
    """
    return f"- 结论: ...\n- 证据: ...\n- 风险: ...\n\n原文长度: {len(text)}"

researcher = Agent(
    role="市场研究员",
    goal="调研 {topic} 的最新趋势并汇总来源",
    backstory="擅长检索与信息整合，注重来源可靠性与去重",
    tools=[structured_summary],
    allow_delegation=False,
    verbose=True,
)

writer = Agent(
    role="内容撰稿人",
    goal="将研究结果写成 500 字中文摘要，结构清晰，引用来源",
    backstory="有新闻写作经验，注重准确性与可读性",
    allow_delegation=False,
    verbose=True,
)

t1 = Task(
    description=(
        "围绕主题“{topic}”整理3-5条关键发现（可模拟已有素材），"
        "并用工具对每条做结构化摘要，最后汇总成一份研究笔记。"
    ),
    expected_output="包含要点与引用的研究笔记（markdown），不少于300字",
    agent=researcher,
)

t2 = Task(
    description=(
        "基于研究笔记撰写500字左右中文摘要，包含：结论、"
        "行业现状、趋势、参考链接。如有不确定性，显式标注。"
    ),
    expected_output="结构化摘要（markdown），长度约500字，末尾列参考链接",
    agent=writer,
)

crew = Crew(
    agents=[researcher, writer],
    tasks=[t1, t2],
    process=Process.sequential,
)

result = crew.kickoff(inputs={"topic": "AIGC 行业"})
print(result)
```

> 说明：示例使用本地 `@tool` 函数，便于在无外网时演示工具调用与多 Agent 协作。接入真实搜索/爬取时，可替换为 `crewai-tools` 的 `SerperApiTool`、`ScrapeWebsiteTool` 等，并配置对应 API Key。

---

## 备忘与注意

- CrewAI 框架强调“独立于其他 Agent 框架”，并提供双轨编排：Crews（自治协作）与 Flows（事件驱动，单次 LLM 调用可达成精细控制），二者可互操作。
- 企业/云版本提供控制平面（Tracing/Observability、RBAC、Agent/Tool 仓库、幻觉防护、集成等）。
- 文档结构显示 Training/Testing/Reasoning/Knowledge/CLI 等专章，建议按需启用、并将关键节点纳入测试与观测体系。

---

## 官方链接（便于查阅）

- Docs: <https://docs.crewai.com>
- GitHub（框架）: <https://github.com/crewAIInc/crewAI>
- GitHub（工具）: <https://github.com/crewAIInc/crewai-tools>
- 社区/课程：<https://learn.crewai.com>、<https://community.crewai.com>

