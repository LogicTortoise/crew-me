# Schema Notes (XML Export)

This project can export a basic travel plan XML intended to align with your external schema files:
- `/Users/bytedance/Documents/Personal/github/always-on-travelling/travel-plan-schema.xml`
- `travel-plan-example.xml`

Given sandbox limits, we do not read or validate against those files automatically. The generated structure is simple and mappable, and you can add validation later if the XSD is locally available.

## Produced XML Shape

```xml
<?xml version="1.0" encoding="utf-8"?>
<TravelPlan version="1.0">
  <Meta>
    <Destination>...</Destination>
    <Days>...</Days>
    <Budget>...</Budget>
    <Preferences>...</Preferences>
    <Summary>...</Summary>
    <Tips>...</Tips>
  </Meta>
  <Days>
    <Day index="1">
      <Note>...</Note>
      <Items>
        <Item period="morning">
          <Title>...</Title>
          <Location>...</Location>
          <Transport>...</Transport>
          <Duration>...</Duration>
          <Cost>...</Cost>
          <Note>...</Note>
        </Item>
        <!-- more items -->
      </Items>
    </Day>
    <!-- more days -->
  </Days>
  
</TravelPlan>
```

## Mapping Guidance
- Root element can be renamed/mapped to your schema’s root if needed.
- `Meta` fields map to the high-level plan attributes.
- Each `Day` contains optional `Note` and an `Items` list. `period` is a coarse tag derived from headings like “上午/下午/晚上”.

## Validation (Optional)
If you want to validate against an XSD:
- Add `lxml` or `xmlschema` to `requirements.txt` and install dependencies.
- Implement an XSD loader and `ElementTree` validator in `travel_xml.py`.

```python
# Example sketch (not included by default):
from lxml import etree
schema = etree.XMLSchema(file="/path/to/travel-plan-schema.xsd")
schema.assertValid(etree.parse(out_xml))
```

## Parser Assumptions
- We parse the Crew’s Markdown by splitting on day headings (e.g., “第1天”, “Day 1”, “D1”) and bullets under each.
- If no headings are detected, we fallback to generating placeholder days with the raw plan text as `Note`.

```
Limitations: without a strict schema or structured JSON from the agent, parsing is best-effort.
```

---

If you’d like, I can wire in strict XSD validation and adjust the element names to exactly match your XML schema once it’s available to this project.

