from typing import Dict, Any

import os
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool

# Reuse tools from travel_agents if present
try:
    from travel_agents import local_search, web_fetch  # type: ignore
except Exception:  # pragma: no cover
    local_search = None
    web_fetch = None


def _get_llm(model_env: str, temperature: float = 0.2) -> LLM:
    model = os.getenv(model_env) or os.getenv("CREWAI_MODEL") or "openai/gpt-4o-mini"
    return LLM(model=model, temperature=temperature)


def build_simple_crew() -> Crew:
    """
    Build a simplified 2-agent crew:
    - Planner: combines research + itinerary planning (may use tools)
    - Presenter: refines and formats output for downstream export
    """

    planner = Agent(
        role="行程规划师（简化）",
        goal=(
            "基于 {destination} / {days} 天 / 预算 {budget} / 偏好 {preferences}，"
            "直接生成逐日可执行行程（上午/下午/晚上），包含地点、通勤与就餐建议。"
        ),
        backstory=(
            "覆盖核心城市与常见玩法，优先同区串联景点，减少折返；遇到高峰或预约场景给出替代。"
        ),
        tools=[t for t in (local_search, web_fetch) if t is not None],
        allow_delegation=False,
        llm=_get_llm("PLANNER_MODEL", temperature=0.2),
        verbose=True,
    )

    presenter = Agent(
        role="行程呈现官（简化）",
        goal=(
            "把规划结果整理成结构化且易读的 Markdown，总结预算分配与每日要点；"
            "必要时补充注意事项与备选方案。"
        ),
        backstory="偏重信息整洁与可执行清单，适合导出与分享。",
        allow_delegation=False,
        llm=_get_llm("PRESENTER_MODEL", temperature=0.0),
        verbose=True,
    )

    plan_task = Task(
        description=(
            "请直接产出 {days} 天的逐日行程，分‘上午/下午/晚上’三段；"
            "每段包含：地点/活动、交通方式、大致时长、就餐建议、可替代项；"
            "结合 {preferences} 与 {budget} 控制节奏，避免跨城或长距离折返；"
            "如可用，请先用‘本地搜索’获取近期闭馆/活动/天气等要点，再整合到行程中。"
        ),
        expected_output="逐日行程的 Markdown 表（按天、按时段分块）",
        agent=planner,
    )

    present_task = Task(
        description=(
            "对上一任务的行程进行清理与补充，并输出结构化 JSON：\n"
            "1) Markdown：‘摘要 + 预算分配建议 + 注意事项 + 每日要点 + 最终行程’\n"
            "2) 追加一个 JSON 代码块（```json ... ```），字段包括：\n"
            "   meta: { title, summary, totalDays, destinations:[string], travelStyle, budget:{currency,totalEstimate,perPerson}, participants:[{id,name,role,departureFrom}] }\n"
            "   timeline: [ { id?, type, day, start, end, durationMinutes?,\n"
            "                activity:{ title, description?, category? },\n"
            "                participants: { all?:bool, sharedTransport?, route? } | { personRefs:[{id, transport?, route?}] },\n"
            "                locations:[{ type?:string, name, address?, coordinates?:{lat,lng} }],\n"
            "                budget?:{ estimated?, category?, perPerson?, breakdown?:[{person?, amount?, text}] } } ]\n"
            "若信息不详可省略字段，但请保持 JSON 语法正确。"
        ),
        expected_output=(
            "Markdown 文档 + 结尾处一个 ```json 代码块，包含 meta 与 timeline 的结构化数据"
        ),
        agent=presenter,
    )

    return Crew(
        agents=[planner, presenter],
        tasks=[plan_task, present_task],
        process=Process.sequential,
        verbose=True,
    )
