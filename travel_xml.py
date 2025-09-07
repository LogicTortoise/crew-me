from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
import xml.etree.ElementTree as ET
import json
import re


# NOTE: We do not strictly validate against the external XSD here to avoid new
# dependencies. The produced XML aims to be close to typical travel-plan schemas
# and is easy to map. If you provide the exact XSD path via env or CLI, we can
# later add validation using lxml or xmlschema.


@dataclass
class PlanItem:
    period: str  # morning|afternoon|evening|other
    title: str
    location: Optional[str] = None
    transport: Optional[str] = None
    duration: Optional[str] = None  # e.g., "120" (minutes)
    cost: Optional[str] = None
    note: Optional[str] = None


@dataclass
class DayPlan:
    index: int
    items: List[PlanItem] = field(default_factory=list)
    note: Optional[str] = None


@dataclass
class TravelPlan:
    destination: str
    days: int
    budget: str
    preferences: str
    summary: Optional[str] = None
    tips: Optional[str] = None
    daily: List[DayPlan] = field(default_factory=list)


@dataclass
class SchemaShape:
    """Describes tag/attr names to align XML to a target schema.

    Defaults mirror the built-in simple schema.
    """
    # Common
    root: str = "TravelPlan"
    ns: Optional[str] = None
    version_value: Optional[str] = None

    # Default-days/items mode
    meta: Optional[str] = "Meta"
    destination: str = "Destination"
    days_tag: str = "Days"
    day_tag: str = "Day"
    day_index_attr: str = "index"
    note: str = "Note"
    items_tag: str = "Items"
    item_tag: str = "Item"
    period_attr: str = "period"
    title: str = "Title"
    location: str = "Location"
    transport: str = "Transport"
    duration: str = "Duration"
    cost: str = "Cost"
    summary: str = "Summary"
    tips: str = "Tips"
    preferences: str = "Preferences"
    budget: str = "Budget"
    days_count: str = "Days"  # used under meta when meta present

    # Timeline-events mode (v2.1 example)
    mode: str = "default"  # "default" | "timeline"
    timeline_tag: str = "Timeline"
    event_tag: str = "Event"
    event_type_attr: str = "type"
    event_id_attr: str = "id"
    timeslot_tag: str = "TimeSlot"
    timeslot_day: str = "Day"
    timeslot_start: str = "StartTime"
    timeslot_end: str = "EndTime"
    timeslot_duration: str = "Duration"
    activity_tag: str = "Activity"
    activity_title: str = "Title"
    activity_desc: str = "Description"
    activity_category: str = "Category"
    meta_title: str = "Title"
    meta_total_days: str = "TotalDays"
    meta_destinations: str = "Destinations"
    meta_city: str = "City"
    meta_travel_style: str = "TravelStyle"
    meta_budget: str = "Budget"
    meta_currency: str = "Currency"
    meta_total_estimate: str = "TotalEstimate"
    meta_per_person: str = "PerPerson"


def _ci_find_child(elem: ET.Element, names: List[str]) -> Optional[ET.Element]:
    # case-insensitive match on localname (strip namespace)
    lookup = { _strip_ns(child.tag).lower(): child for child in list(elem) }
    for n in names:
        c = lookup.get(n.lower())
        if c is not None:
            return c
    return None


def _strip_ns(tag: str) -> str:
    return tag.split('}')[-1] if '}' in tag else tag


def _infer_shape_from_example(xml_path: str) -> SchemaShape:
    """Heuristically infer a shape from an example XML inside the workspace."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        ns = None
        if root.tag.startswith('{'):
            ns = root.tag.split('}')[0][1:]
        shape = SchemaShape(root=_strip_ns(root.tag), ns=ns)
        # read version attribute if present
        if 'version' in root.attrib:
            shape.version_value = root.attrib.get('version')

        # Try to find days container
        # Timeline structure?
        timeline = _ci_find_child(root, ["Timeline", "timeline"]) 
        if timeline is not None and len(list(timeline)):
            shape.mode = "timeline"
            shape.timeline_tag = _strip_ns(timeline.tag)
            first_event = list(timeline)[0]
            shape.event_tag = _strip_ns(first_event.tag)
            # Meta
            meta = _ci_find_child(root, ["Meta", "meta", "Info", "Header"])
            if meta is not None:
                shape.meta = _strip_ns(meta.tag)
            else:
                shape.meta = None
            return shape

        # Default days/items structure
        days = _ci_find_child(root, ["Days", "days", "Itinerary", "Itineraries", "Schedule", "Schedules"])
        if days is not None:
            shape.days_tag = _strip_ns(days.tag)
            # day element
            if len(list(days)):
                first_day = list(days)[0]
                shape.day_tag = _strip_ns(first_day.tag)
                # index attr
                if "index" in first_day.attrib:
                    shape.day_index_attr = "index"
                elif "day" in first_day.attrib:
                    shape.day_index_attr = "day"
                # items container
                items = _ci_find_child(first_day, ["Items", "items", "Plan", "Plans", "Activities", "ActivityList"])
                if items is not None:
                    shape.items_tag = _strip_ns(items.tag)
                    if len(list(items)):
                        shape.item_tag = _strip_ns(list(items)[0].tag)

        # Meta or top-level fields
        meta = _ci_find_child(root, ["Meta", "meta", "Info", "Header"])
        if meta is not None:
            shape.meta = _strip_ns(meta.tag)
        else:
            shape.meta = None  # write fields at root

        return shape
    except Exception:
        return SchemaShape()


def _shape_from_map(mapping: Dict[str, str]) -> SchemaShape:
    s = SchemaShape()
    for k, v in mapping.items():
        if hasattr(s, k) and isinstance(v, str):
            setattr(s, k, v)
    return s


def _detect_period(line: str) -> str:
    line = line.lower()
    if any(k in line for k in ["上午", "morning"]):
        return "morning"
    if any(k in line for k in ["下午", "afternoon"]):
        return "afternoon"
    if any(k in line for k in ["晚上", "evening", "夜"]):
        return "evening"
    return "other"


def _extract_duration_minutes(text: str) -> Optional[int]:
    # 匹配 "2小时", "2.5小时", "120分钟", "90min", "2h"
    m = re.search(r"(\d+(?:\.\d+)?)\s*(小时|h|小时钟|hr|hrs)", text)
    if m:
        hours = float(m.group(1))
        return int(hours * 60)
    m = re.search(r"(\d+)\s*(分钟|min|mins)", text)
    if m:
        return int(m.group(1))
    return None


def _extract_transport(text: str) -> Optional[str]:
    # 简单关键词识别
    pairs = [
        ("地铁", "subway"),
        ("公交", "bus"),
        ("步行", "walk"),
        ("出租", "taxi"),
        ("打车", "taxi"),
        ("自驾", "drive"),
        ("高铁", "rail"),
        ("火车", "rail"),
        ("飞机", "flight"),
    ]
    for k, v in pairs:
        if k in text:
            return v
    return None


def _split_title_and_note(text: str) -> Tuple[str, Optional[str]]:
    # 形如 "西湖（咖啡/早市）" → 标题: 西湖, 备注: 咖啡/早市
    # 或者 "西湖 - 徒步路线" → 标题: 西湖, 备注: 徒步路线
    text = text.strip().strip('。')
    m = re.match(r"^(.*?)[（(](.*?)[）)]\s*$", text)
    if m:
        title = m.group(1).strip()
        note = m.group(2).strip()
        return title or text, note or None
    if "-" in text:
        parts = [p.strip() for p in text.split("-", 1)]
        if len(parts) == 2 and parts[0] and parts[1]:
            return parts[0], parts[1]
    return text, None


def parse_markdown_days(md: str, total_days: int) -> List[DayPlan]:
    """Very lightweight parser to split markdown by day headings and extract bullets.
    Accepts headings like: Day 1 / 第1天 / D1 / Day1.
    """
    # Split by day-like headings
    pattern = re.compile(r"^(?:#+\s*)?(第?\s*(\d+)\s*天|day\s*(\d+)|d\s*(\d+))\b",
                         flags=re.IGNORECASE | re.MULTILINE)
    parts = []
    last = 0
    for m in pattern.finditer(md):
        idx = m.start()
        if parts:
            parts[-1][2] = idx  # set end
        num = int(next(g for g in m.groups()[1:] if g) or "0")
        parts.append([num, m.end(), len(md)])
    if not parts:
        # Fallback: single day block
        return [DayPlan(index=i + 1, note=md.strip()) for i in range(total_days)]

    # Extract blocks
    blocks: List[DayPlan] = []
    for num, start, end in parts:
        chunk = md[start:end].strip()
        # Extract bullet lines as items
        items: List[PlanItem] = []
        for line in chunk.splitlines():
            l = line.strip().lstrip("-•*").strip()
            if not l:
                continue
            if len(l) < 2:
                continue
            period = _detect_period(l)
            title, note = _split_title_and_note(l)
            dur = _extract_duration_minutes(l)
            transport = _extract_transport(l)
            items.append(PlanItem(period=period, title=title, note=note, duration=(str(dur) if dur else None), transport=transport))
        blocks.append(DayPlan(index=num, items=items, note=None if items else chunk))

    # Ensure continuous days up to total_days
    by_num = {b.index: b for b in blocks}
    result: List[DayPlan] = []
    for i in range(1, total_days + 1):
        result.append(by_num.get(i, DayPlan(index=i, note="")))
    return result


def build_xml(plan: TravelPlan, shape: Optional[SchemaShape] = None) -> ET.Element:
    s = shape or SchemaShape()

    def q(name: str) -> str:
        return f"{{{s.ns}}}{name}" if s.ns else name

    if s.ns:
        # register default namespace to avoid ns0 prefix
        ET.register_namespace('', s.ns)

    version_attr = s.version_value or "1.0"
    root = ET.Element(q(s.root), attrib={"version": version_attr})

    # Timeline-based schema
    if s.mode == "timeline":
        # Meta
        parent_for_fields = root
        if s.meta:
            parent_for_fields = ET.SubElement(root, q(s.meta))
        # Basic fields
        ET.SubElement(parent_for_fields, q(s.meta_title)).text = f"{plan.destination} {plan.days}天行程"
        if plan.summary:
            ET.SubElement(parent_for_fields, q(s.summary)).text = plan.summary
        else:
            ET.SubElement(parent_for_fields, q(s.summary)).text = f"偏好：{plan.preferences}；预算：{plan.budget}"
        ET.SubElement(parent_for_fields, q(s.meta_total_days)).text = str(plan.days)
        dests_el = ET.SubElement(parent_for_fields, q(s.meta_destinations))
        ET.SubElement(dests_el, q(s.meta_city)).text = plan.destination
        ET.SubElement(parent_for_fields, q(s.meta_travel_style)).text = plan.preferences
        budget_el = ET.SubElement(parent_for_fields, q(s.meta_budget))
        ET.SubElement(budget_el, q(s.meta_currency)).text = "CNY"
        # optional estimates could be added later

        # Timeline events
        timeline = ET.SubElement(root, q(s.timeline_tag))
        # default times per period
        def time_range(period: str) -> (str, str):
            if period == "morning":
                return "09:00", "12:00"
            if period == "afternoon":
                return "13:30", "17:00"
            if period == "evening":
                return "18:30", "21:00"
            return "10:00", "12:00"

        def event_type(period: str) -> str:
            if period in ("morning", "afternoon"):
                return "attraction"
            if period == "evening":
                return "dining"
            return "custom"

        for d in plan.daily:
            if not d.items:
                # create a rest event with note
                ev = ET.SubElement(timeline, q(s.event_tag), attrib={s.event_id_attr: f"d{d.index}-rest", s.event_type_attr: "rest"})
                ts = ET.SubElement(ev, q(s.timeslot_tag))
                ET.SubElement(ts, q(s.timeslot_day)).text = str(d.index)
                ET.SubElement(ts, q(s.timeslot_start)).text = "10:00"
                act = ET.SubElement(ev, q(s.activity_tag))
                ET.SubElement(act, q(s.activity_title)).text = "自由活动/休息"
                if d.note:
                    ET.SubElement(act, q(s.activity_desc)).text = d.note
                continue

            for idx, it in enumerate(d.items, 1):
                etype = event_type(it.period)
                ev = ET.SubElement(timeline, q(s.event_tag), attrib={s.event_id_attr: f"d{d.index}-{idx}", s.event_type_attr: etype})
                ts = ET.SubElement(ev, q(s.timeslot_tag))
                ET.SubElement(ts, q(s.timeslot_day)).text = str(d.index)
                start, end = time_range(it.period)
                ET.SubElement(ts, q(s.timeslot_start)).text = start
                ET.SubElement(ts, q(s.timeslot_end)).text = end
                # duration if present
                if it.duration and it.duration.isdigit():
                    ET.SubElement(ts, q(s.timeslot_duration)).text = it.duration

                act = ET.SubElement(ev, q(s.activity_tag))
                ET.SubElement(act, q(s.activity_title)).text = it.title
                # category by period fallback
                cat = "景点" if etype == "attraction" else ("餐饮" if etype == "dining" else "活动")
                ET.SubElement(act, q(s.activity_category)).text = cat
                if it.note:
                    ET.SubElement(act, q(s.activity_desc)).text = it.note
                # optional participants/locations based on heuristics
                if it.transport:
                    # Use Participants/SharedTransport for simplicity
                    parts = _ci_find_child(ev, ["Participants"]) or ET.SubElement(ev, q("Participants"))
                    ET.SubElement(parts, q("SharedTransport")).text = it.transport
        return root

    # Default days/items schema
    parent_for_fields = root
    if s.meta:
        parent_for_fields = ET.SubElement(root, q(s.meta))
    ET.SubElement(parent_for_fields, q(s.destination)).text = plan.destination
    if s.meta and s.days_count:
        ET.SubElement(parent_for_fields, q(s.days_count)).text = str(plan.days)
    ET.SubElement(parent_for_fields, q(s.budget)).text = plan.budget
    ET.SubElement(parent_for_fields, q(s.preferences)).text = plan.preferences
    if plan.summary:
        ET.SubElement(parent_for_fields, q(s.summary)).text = plan.summary
    if plan.tips:
        ET.SubElement(parent_for_fields, q(s.tips)).text = plan.tips

    days_el = ET.SubElement(root, q(s.days_tag))
    for d in plan.daily:
        d_el = ET.SubElement(days_el, q(s.day_tag), attrib={s.day_index_attr: str(d.index)})
        if d.note:
            ET.SubElement(d_el, q(s.note)).text = d.note
        items_el = ET.SubElement(d_el, q(s.items_tag))
        for it in d.items:
            it_el = ET.SubElement(items_el, q(s.item_tag), attrib={s.period_attr: it.period})
            ET.SubElement(it_el, q(s.title)).text = it.title
            if it.location:
                ET.SubElement(it_el, q(s.location)).text = it.location
            if it.transport:
                ET.SubElement(it_el, q(s.transport)).text = it.transport
            if it.duration:
                ET.SubElement(it_el, q(s.duration)).text = it.duration
            if it.cost:
                ET.SubElement(it_el, q(s.cost)).text = it.cost
            if it.note:
                ET.SubElement(it_el, q(s.note)).text = it.note

    return root


def export_xml(
    destination: str,
    days: int,
    budget: str,
    preferences: str,
    markdown_plan: str,
    summary: Optional[str] = None,
    tips: Optional[str] = None,
    schema_example: Optional[str] = None,
    schema_map: Optional[str] = None,
) -> ET.ElementTree:
    # Determine schema shape
    shape: Optional[SchemaShape] = None
    try:
        if schema_map and os.path.isfile(schema_map):
            with open(schema_map, "r", encoding="utf-8") as f:
                mapping = json.load(f)
            shape = _shape_from_map(mapping)
        elif schema_example and os.path.isfile(schema_example):
            shape = _infer_shape_from_example(schema_example)
    except Exception:
        shape = None

    # Try structured JSON block inside markdown
    plan_json = _extract_plan_json(markdown_plan)
    if plan_json is not None:
        root = build_xml_from_json(plan_json, fallback_meta={
            "destination": destination,
            "totalDays": days,
            "budget": budget,
            "travelStyle": preferences,
            "summary": summary,
        }, shape=shape)
        return ET.ElementTree(root)

    # Fallback: parse markdown heuristics
    daily = parse_markdown_days(markdown_plan, days)
    tp = TravelPlan(
        destination=destination,
        days=days,
        budget=budget,
        preferences=preferences,
        summary=summary,
        tips=tips,
        daily=daily,
    )
    root = build_xml(tp, shape)
    return ET.ElementTree(root)


def _extract_plan_json(md: str) -> Optional[Dict[str, any]]:
    m = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", md)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def build_xml_from_json(data: Dict[str, any], fallback_meta: Dict[str, any], shape: Optional[SchemaShape]) -> ET.Element:
    s = shape or SchemaShape()

    def q(name: str) -> str:
        return f"{{{s.ns}}}{name}" if s.ns else name

    if s.ns:
        ET.register_namespace('', s.ns)

    version_attr = s.version_value or "1.0"
    root = ET.Element(q(s.root), attrib={"version": version_attr})

    # Meta
    meta = data.get("meta", {}) or {}
    parent = root
    if s.meta:
        parent = ET.SubElement(root, q(s.meta))
    title = meta.get("title") or f"{fallback_meta.get('destination','')} {fallback_meta.get('totalDays','')}天行程"
    ET.SubElement(parent, q("Title")).text = str(title)
    summary_text = meta.get("summary") or str(fallback_meta.get("summary") or "") or f"偏好：{fallback_meta.get('travelStyle','')}；预算：{fallback_meta.get('budget','')}"
    if summary_text:
        ET.SubElement(parent, q("Summary")).text = summary_text
    total_days = meta.get("totalDays") or fallback_meta.get("totalDays")
    if total_days:
        ET.SubElement(parent, q("TotalDays")).text = str(total_days)

    dests = meta.get("destinations") or [fallback_meta.get("destination")] if fallback_meta.get("destination") else []
    if dests:
        dests_el = ET.SubElement(parent, q("Destinations"))
        for city in dests:
            ET.SubElement(dests_el, q("City")).text = str(city)

    travel_style = meta.get("travelStyle") or fallback_meta.get("travelStyle")
    if travel_style:
        ET.SubElement(parent, q("TravelStyle")).text = str(travel_style)

    # Meta participants
    participants = meta.get("participants") or []
    if participants:
        parts_el = ET.SubElement(parent, q("Participants"))
        for p in participants:
            pel = ET.SubElement(parts_el, q("Person"), attrib={"id": str(p.get("id"))} if p.get("id") else {})
            if p.get("name"):
                ET.SubElement(pel, q("Name")).text = str(p.get("name"))
            if p.get("role"):
                ET.SubElement(pel, q("Role")).text = str(p.get("role"))
            if p.get("departureFrom"):
                ET.SubElement(pel, q("DepartureFrom")).text = str(p.get("departureFrom"))

    # Meta budget
    budget_meta = meta.get("budget") or {}
    if any(k in budget_meta for k in ("currency", "totalEstimate", "perPerson")):
        be = ET.SubElement(parent, q("Budget"))
        if budget_meta.get("currency"):
            ET.SubElement(be, q("Currency")).text = str(budget_meta.get("currency"))
        if budget_meta.get("totalEstimate") is not None:
            ET.SubElement(be, q("TotalEstimate")).text = str(budget_meta.get("totalEstimate"))
        if budget_meta.get("perPerson") is not None:
            ET.SubElement(be, q("PerPerson")).text = str(budget_meta.get("perPerson"))

    # Timeline
    timeline = ET.SubElement(root, q(s.timeline_tag))
    events = data.get("timeline") or []
    for i, evd in enumerate(events, 1):
        etype = str(evd.get("type") or "custom")
        eid = str(evd.get("id") or f"e{i}")
        ev = ET.SubElement(timeline, q(s.event_tag), attrib={s.event_id_attr: eid, s.event_type_attr: etype})

        # TimeSlot
        ts = ET.SubElement(ev, q(s.timeslot_tag))
        if evd.get("day") is not None:
            ET.SubElement(ts, q(s.timeslot_day)).text = str(evd.get("day"))
        if evd.get("start"):
            ET.SubElement(ts, q(s.timeslot_start)).text = str(evd.get("start"))
        if evd.get("end"):
            ET.SubElement(ts, q(s.timeslot_end)).text = str(evd.get("end"))
        if evd.get("durationMinutes") is not None:
            ET.SubElement(ts, q(s.timeslot_duration)).text = str(evd.get("durationMinutes"))

        # Activity
        act = evd.get("activity") or {}
        act_el = ET.SubElement(ev, q(s.activity_tag))
        if act.get("title"):
            ET.SubElement(act_el, q(s.activity_title)).text = str(act.get("title"))
        if act.get("description"):
            ET.SubElement(act_el, q(s.activity_desc)).text = str(act.get("description"))
        if act.get("category"):
            ET.SubElement(act_el, q(s.activity_category)).text = str(act.get("category"))
        if act.get("highlights"):
            h = ET.SubElement(act_el, q("Highlights"))
            for it in act.get("highlights"):
                ET.SubElement(h, q("Item")).text = str(it)

        # Participants (either personRefs or sharedTransport/route or all)
        parts = evd.get("participants") or {}
        if parts:
            pel = ET.SubElement(ev, q("Participants"))
            if parts.get("all"):
                pel.attrib["all"] = "true"
            prs = parts.get("personRefs") or []
            if prs:
                for pr in prs:
                    pre = ET.SubElement(pel, q("PersonRef"), attrib={"id": str(pr.get("id"))} if pr.get("id") else {})
                    if pr.get("transport"):
                        ET.SubElement(pre, q("Transport")).text = str(pr.get("transport"))
                    if pr.get("route"):
                        ET.SubElement(pre, q("Route")).text = str(pr.get("route"))
            else:
                if parts.get("sharedTransport"):
                    ET.SubElement(pel, q("SharedTransport")).text = str(parts.get("sharedTransport"))
                if parts.get("route"):
                    ET.SubElement(pel, q("Route")).text = str(parts.get("route"))

        # Locations
        locs = evd.get("locations") or []
        if locs:
            le = ET.SubElement(ev, q("Locations"))
            for loc in locs:
                attrs = {"type": str(loc.get("type"))} if loc.get("type") else {}
                l = ET.SubElement(le, q("Location"), attrib=attrs)
                if loc.get("name"):
                    ET.SubElement(l, q("Name")).text = str(loc.get("name"))
                if loc.get("address"):
                    ET.SubElement(l, q("Address")).text = str(loc.get("address"))
                coords = loc.get("coordinates") or {}
                if set(coords.keys()) & {"lat", "lng"}:
                    c = ET.SubElement(l, q("Coordinates"))
                    if coords.get("lat") is not None:
                        c.attrib["lat"] = str(coords.get("lat"))
                    if coords.get("lng") is not None:
                        c.attrib["lng"] = str(coords.get("lng"))

        # Event Budget
        bev = evd.get("budget") or {}
        if bev:
            be = ET.SubElement(ev, q("Budget"))
            if bev.get("estimated") is not None:
                ET.SubElement(be, q("Estimated")).text = str(bev.get("estimated"))
            if bev.get("category"):
                ET.SubElement(be, q("Category")).text = str(bev.get("category"))
            if bev.get("perPerson") is not None:
                ET.SubElement(be, q("PerPerson")).text = str(bev.get("perPerson"))
            if bev.get("breakdown"):
                br = ET.SubElement(be, q("Breakdown"))
                for item in bev.get("breakdown"):
                    ie = ET.SubElement(br, q("Item"))
                    if item.get("person"):
                        ie.attrib["person"] = str(item.get("person"))
                    if item.get("amount") is not None:
                        ie.attrib["amount"] = str(item.get("amount"))
                    ie.text = str(item.get("text") or "")

    return root


def save_xml(tree: ET.ElementTree, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tree.write(path, encoding="utf-8", xml_declaration=True)
