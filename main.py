#!/usr/bin/env python
import argparse
import io
import os
import sys
from datetime import datetime
import json as _json

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from travel_agents import build_crew
from simple_agents import build_simple_crew
from travel_xml import export_xml, save_xml
from dotenv import load_dotenv


class Tee(io.TextIOBase):
    """Duplicate writes to stdout and a file for simple logging."""

    def __init__(self, stream: io.TextIOBase, log_path: str) -> None:
        self.stream = stream
        self.log_file = open(log_path, "a", encoding="utf-8")

    def write(self, s: str) -> int:
        self.stream.write(s)
        self.log_file.write(s)
        return len(s)

    def flush(self) -> None:
        self.stream.flush()
        self.log_file.flush()

    def close(self) -> None:
        try:
            self.log_file.close()
        finally:
            pass


def _print_banner(console: Console) -> None:
    table = Table.grid(expand=True)
    table.add_column(justify="center")
    table.add_row("🌏 Multi‑Agent Travel Planner (CrewAI)")
    console.print(Panel.fit(table, border_style="cyan"))


def _offline_generate_markdown(destination: str, days: int, budget: str, preferences: str) -> str:
    lines = [
        f"# {destination} · {days}天行程（离线简版）",
        "",
        f"- 预算：{budget}",
        f"- 偏好：{preferences}",
        "",
        "## 摘要",
        "基于偏好给出同片区串联、步行为主的轻量行程；如下为每日上午/下午/晚上三段建议。",
    ]
    for i in range(1, days + 1):
        lines += [
            "",
            f"## 第{i}天",
            "- 上午：市区核心片区徒步（咖啡/早市）",
            "- 下午：近郊自然点/展馆（公共交通，避高峰）",
            "- 晚上：回到住宿周边美食街，早收尾休息",
        ]
    # Append a minimal structured JSON block for robust XML export
    events = []
    for d in range(1, days + 1):
        events.append({
            "type": "attraction", "day": d, "start": "09:00", "end": "12:00",
            "activity": {"title": "上午：市区核心片区徒步", "description": "咖啡/早市", "category": "景点"},
            "participants": {"sharedTransport": "walk"}
        })
        events.append({
            "type": "attraction", "day": d, "start": "13:30", "end": "17:00",
            "activity": {"title": "下午：近郊自然点/展馆", "description": "公共交通，避高峰", "category": "景点"},
            "participants": {"sharedTransport": "bus"}
        })
        events.append({
            "type": "dining", "day": d, "start": "18:30", "end": "21:00",
            "activity": {"title": "晚上：回到住宿周边美食街，早收尾休息", "category": "餐饮"}
        })
    plan_json = {
        "meta": {
            "title": f"{destination} {days}天行程",
            "summary": f"偏好：{preferences}；预算：{budget}",
            "totalDays": days,
            "destinations": [destination],
            "travelStyle": preferences,
            "budget": {"currency": "CNY"}
        },
        "timeline": events
    }
    lines += [
        "",
        "```json",
        _json.dumps(plan_json, ensure_ascii=False, indent=2),
        "```",
    ]
    return "\n".join(lines)


def plan_once(console: Console, args) -> str:
    # Collect inputs
    destination = args.destination or Prompt.ask("目的地", default="东京")
    days = int(args.days or Prompt.ask("行程天数", default="3"))
    budget = args.budget or Prompt.ask("预算（如：节省/适中/宽松 或 金额区间）", default="适中")
    preferences = args.preferences or Prompt.ask(
        "偏好（如：美食/博物馆/乐园/步行/亲子/小资）", default="美食, 博物馆"
    )

    change_request = getattr(args, "change_request", None) or ""

    # Build crew and kickoff
    use_simple = bool(getattr(args, "simple", False))
    crew = build_simple_crew() if use_simple else build_crew()
    console.print("[bold cyan]⏳ 正在生成行程...（已开启详细日志）[/bold cyan]")
    try:
        result = crew.kickoff(
            inputs={
                "destination": destination,
                "days": days,
                "budget": budget,
                "preferences": preferences,
                "change_request": change_request,
            }
        )
    except Exception as e:
        console.print(f"[yellow]LLM/网络调用失败，使用离线简版：{e}[/yellow]")
        result = _offline_generate_markdown(destination, days, budget, preferences)

    console.print(Panel.fit("📑 最终行程如下", border_style="green"))
    console.print(result)

    # Optional export to XML/Markdown files
    out_md = args.output_md or os.path.join("outputs", "travel_plan.md")
    out_xml = args.output_xml or os.path.join("outputs", "travel_plan.xml")
    try:
        os.makedirs(os.path.dirname(out_md), exist_ok=True)
        with open(out_md, "w", encoding="utf-8") as f:
            f.write(str(result))
    except Exception as e:
        console.print(f"[yellow]写入 Markdown 失败：{e}[/yellow]")

    try:
        tree = export_xml(
            destination=destination,
            days=days,
            budget=budget,
            preferences=preferences,
            markdown_plan=str(result),
            summary=None,
            tips=getattr(args, "change_request", None) or None,
            schema_example=args.schema_example,
            schema_map=args.schema_map,
        )
        save_xml(tree, out_xml)
        console.print(f"[green]已导出 XML：{out_xml}[/green]")
    except Exception as e:
        console.print(f"[yellow]导出 XML 失败：{e}[/yellow]")

    return result


def main() -> None:
    # Load environment variables from .env (project root)
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="最小多 Agent 旅游攻略 CLI（含详细日志输出）"
    )
    parser.add_argument("--destination", help="目的地，如：东京/大阪/巴黎")
    parser.add_argument("--days", help="行程天数，如：3")
    parser.add_argument("--budget", help="预算偏好，如：适中/节省/宽松 或 金额")
    parser.add_argument("--preferences", help="偏好标签，逗号分隔")
    parser.add_argument("--log-file", help="日志文件路径（默认 logs/travel.log）")
    parser.add_argument("--once", action="store_true", help="仅运行一次，不进入交互循环")
    parser.add_argument("--model", help="覆盖默认模型（等价于环境变量 CREWAI_MODEL）")
    parser.add_argument("--researcher-model", help="覆盖研究员模型（等价于环境变量 RESEARCHER_MODEL）")
    parser.add_argument("--planner-model", help="覆盖规划师模型（等价于环境变量 PLANNER_MODEL）")
    parser.add_argument("--reviewer-model", help="覆盖审稿人模型（等价于环境变量 REVIEWER_MODEL）")
    parser.add_argument("--presenter-model", help="覆盖呈现官模型（等价于环境变量 PRESENTER_MODEL）")
    parser.add_argument("--simple", action="store_true", help="使用简化 2-Agent 流程")
    parser.add_argument("--output-xml", help="导出 XML 路径（默认 outputs/travel_plan.xml）")
    parser.add_argument("--output-md", help="导出 Markdown 路径（默认 outputs/travel_plan.md）")
    parser.add_argument("--schema-example", help="工作区内的示例 XML，用于推断目标 schema 结构")
    parser.add_argument("--schema-map", help="JSON 键值映射文件，精确指定标签名/属性名映射")
    args = parser.parse_args()

    # Setup console and logging (tee stdout)
    console = Console()
    _print_banner(console)

    log_file = args.log_file or os.path.join("logs", "travel.log")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n===== Session started at {timestamp} =====\n")

    tee = Tee(sys.stdout, log_file)
    sys.stdout = tee  # simple tee for CrewAI verbose prints

    try:
        # Optional model override via CLI
        if args.model:
            os.environ["CREWAI_MODEL"] = args.model
        if args.researcher_model:
            os.environ["RESEARCHER_MODEL"] = args.researcher_model
        if args.planner_model:
            os.environ["PLANNER_MODEL"] = args.planner_model
        if args.reviewer_model:
            os.environ["REVIEWER_MODEL"] = args.reviewer_model
        if args.presenter_model:
            os.environ["PRESENTER_MODEL"] = args.presenter_model
        if args.once:
            plan_once(console, args)
            return

        # Interactive loop
        last_inputs = {}
        while True:
            console.rule("新一次行程规划")
            result = plan_once(console, args)

            # Keep last inputs for modifications
            last_inputs = {
                "destination": args.destination,
                "days": args.days,
                "budget": args.budget,
                "preferences": args.preferences,
            }

            next_action = Prompt.ask(
                "输入修改请求继续，或输入 'exit' 退出",
                default="",
            ).strip()
            if next_action.lower() in {"exit", "quit", "q"}:
                console.print("👋 已退出。日志已写入文件。")
                break

            # Re-run with change request
            setattr(args, "change_request", next_action)
    except KeyboardInterrupt:
        console.print("\n👋 已取消。日志已写入文件。")
    finally:
        try:
            tee.close()
        except Exception:
            pass
        sys.stdout = sys.__stdout__


if __name__ == "__main__":
    main()
