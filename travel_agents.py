from typing import Dict, Any

import os
import json
from urllib.parse import urlencode, quote_plus
import requests
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool


# No offline mock DB. All live info should go through local_search.


@tool("本地搜索")
def local_search(query: str, format: str = "json") -> str:
    """
    使用本地搜索服务检索实时信息。
    默认请求: http://localhost:10004/search?q=...&format=json
    可用环境变量 LOCAL_SEARCH_BASE_URL 覆盖，示例: http://localhost:10004/search

    输入: query（任意查询，如“深圳今天天气”）
    输出: 将 JSON 结果提炼为简要要点；若无法解析 JSON，返回原始文本（截断）。
    """
    base = os.getenv("LOCAL_SEARCH_BASE_URL", "http://localhost:10004/search")
    try:
        params = {"q": query, "format": format}
        url = f"{base}?{urlencode(params, quote_via=quote_plus)}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()

        ctype = resp.headers.get("Content-Type", "")
        text = resp.text
        # 尝试解析 JSON
        data = None
        if "json" in ctype or text.strip().startswith(('{', '[')):
            try:
                data = resp.json()
            except Exception:
                data = None

        if data is None:
            # 纯文本返回，做截断
            snippet = text if len(text) <= 1200 else text[:1200] + "..."
            return f"[search:raw]\n{snippet}"

        # 尝试通用结构化提取
        # 兼容常见字段: results/items/data，与 title/summary/url/score 等
        items = []
        for key in ("results", "items", "data"):
            if isinstance(data, dict) and key in data and isinstance(data[key], list):
                items = data[key]
                break
        if not items and isinstance(data, list):
            items = data

        lines = [f"[search:query] {query}"]
        if items:
            for i, it in enumerate(items[:5], 1):
                if isinstance(it, dict):
                    title = it.get("title") or it.get("name") or it.get("headline") or "(no-title)"
                    summary = it.get("summary") or it.get("snippet") or it.get("description") or ""
                    url = it.get("url") or it.get("link") or ""
                    part = f"{i}. {title}\n   {summary}"
                    if url:
                        part += f"\n   {url}"
                else:
                    part = f"{i}. {str(it)[:300]}"
                lines.append(part)
        else:
            # 无结构化条目，返回压缩 JSON 片段
            compact = json.dumps(data, ensure_ascii=False)[:1200]
            lines.append(f"[search:json] {compact}")

        return "\n".join(lines)

    except requests.HTTPError as e:
        return f"[search:error] HTTP {e.response.status_code}: {e.response.text[:400]}"
    except Exception as e:
        return f"[search:error] {type(e).__name__}: {e}"


def _get_llm(model_env: str, temperature: float = 0.2) -> LLM:
    """Create a real LLM from env model name. Example: 'openai/gpt-4o-mini'."""
    model = os.getenv(model_env) or os.getenv("CREWAI_MODEL") or "openai/gpt-4o-mini"
    return LLM(model=model, temperature=temperature)


def build_crew() -> Crew:
    """Create a minimal multi-agent crew for travel planning."""

    researcher_llm = _get_llm("RESEARCHER_MODEL", temperature=0.2)

    researcher = Agent(
        role="旅行研究员",
        goal=(
            "针对 {destination} 的旅行，基于工具与已知信息整理城市画像、"
            "核心景点、通行方式、就餐选择与大致花费边界。"
        ),
        backstory=(
            "资深自由行博主，擅长按地铁/步行路径串联景点，关注高峰时段与预约机制。"
        ),
        tools=[local_search],
        allow_delegation=False,
        llm=researcher_llm,
        verbose=True,
    )

    planner_llm = _get_llm("PLANNER_MODEL", temperature=0.2)

    planner = Agent(
        role="行程规划师",
        goal=(
            "把研究资料转化为逐日可执行行程，兼顾通勤效率、密度与休息，"
            "并结合 {preferences} 与预算 {budget} 控制节奏。"
        ),
        backstory=(
            "熟悉欧洲与日本主要城市的分区动线，善于把景点按地理位置聚类，"
            "减少折返，给出明确时间块与就餐建议。"
        ),
        allow_delegation=False,
        llm=planner_llm,
        verbose=True,
    )

    reviewer_llm = _get_llm("REVIEWER_MODEL", temperature=0.0)

    reviewer = Agent(
        role="旅行审稿人",
        goal=(
            "审查行程是否可行、是否过度奔波、是否忽略预约/排队等刚性约束；"
            "给出改进版最终行程。"
        ),
        backstory="有带团经验，擅长把控节奏与风险点，强调备选方案。",
        allow_delegation=False,
        llm=reviewer_llm,
        verbose=True,
    )

    research_task = Task(
        description=(
            "请针对“{destination}”进行线下资料归纳：\n"
            "1) 城市画像（分区/交通/就餐/花费等概览）\n"
            "2) 3-6 个核心景点（聚合相邻片区）\n"
            "3) 交通方式与预约要点\n"
            "务必调用‘本地搜索’工具获取实时要点（如天气/活动/闭馆提醒/突发情况），"
            "示例：‘{destination} 天气’、‘{destination} 博物馆 闭馆’、‘{destination} 活动’ 等关键词。"
        ),
        expected_output=(
            "一份结构化研究笔记（markdown）：城市画像/必看片区/交通与预约/预算提示"
        ),
        agent=researcher,
    )

    plan_task = Task(
        description=(
            "基于研究笔记，为 {days} 天行程输出逐日计划（时间块：上午/下午/晚上），"
            "每块包含：地点、交通方式、时长、就餐建议、可替代项；"
            "结合偏好 {preferences} 与预算 {budget} 控制节奏，避免跨城/长距离折返。"
        ),
        expected_output=(
            "一个按天划分的行程表（markdown），每日 3 段，含通勤与注意事项。"
        ),
        agent=planner,
    )

    review_task = Task(
        description=(
            "审查行程可行性与风险（预约/高峰/闭馆/天气），提出改进并给出最终版本。"
            "若发现不合理密度或不连贯动线，进行重排并标注变更原因。"
            "若用户给出 `change_request`，需基于其要求微调后输出最终版。"
        ),
        expected_output=(
            "改进说明 + 最终行程（markdown），确保可执行与节奏合理。"
        ),
        agent=reviewer,
    )

    crew = Crew(
        agents=[researcher, planner, reviewer],
        tasks=[research_task, plan_task, review_task],
        process=Process.sequential,
        verbose=True,
    )
    return crew
