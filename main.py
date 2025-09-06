#!/usr/bin/env python
import argparse
import io
import os
import sys
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from travel_agents import build_crew
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
    crew = build_crew()
    console.print("[bold cyan]⏳ 正在生成行程...（已开启详细日志）[/bold cyan]")
    result = crew.kickoff(
        inputs={
            "destination": destination,
            "days": days,
            "budget": budget,
            "preferences": preferences,
            "change_request": change_request,
        }
    )

    console.print(Panel.fit("📑 最终行程如下", border_style="green"))
    console.print(result)
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
