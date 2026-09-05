"""Task family registry — the OPEN task space.

A family is a callable `gen(rng, ctx) -> (unit_dict, world_extra)` where:
  unit_dict   : a TaskUnit (see spec/task-unit.schema.json)
  world_extra : {env_id: {"kind": ..., "state": ...}} added to the session world

Families are pluggable: registering a new family extends the space; nothing
about the harness hard-codes a closed task list. That is how the space stays
*countless* — mixture combinatorics + community families + dynamic injection.
"""

from __future__ import annotations

import random

CITIES = ["Ningbo", "Hangzhou", "Shanghai", "Chengdu", "Suzhou"]
NAMES = ["Lea", "Marcus", "Priya", "Jonas", "Mei", "Amir", "Sofia"]
TOPICS = ["battery recycling markets", "protein bar brand analysis", "regional EV charging policy",
          "smart-home sensor supply chains", "coastal freight costs"]


# --------------------------------------------------------------------------
# family: research_memo
# --------------------------------------------------------------------------

def gen_research_memo(rng: random.Random, ctx: dict):
    topic = rng.choice(TOPICS)
    doc_market = {"name": f"{topic}.md", "text": f"notes on {topic}:\n- 2025 global size ~ 18B USD\n- CAGR ~ 12%\n- top region: North America\n- key constraint: regulation lag"[:400]}
    doc_notes = {"name": "context.md", "text": f"client asks: quantify market, name top region, give one risk.\n- risk: regulation lag\n- target: chilled, factual memo"[:200]}
    tickers = {"WRE": {"price": 42.5, "note": "waste recycler"}, "EVB": {"price": 7.2, "note": "battery pack maker"}}
    fact_price = round(tickers["WRE"]["price"] + rng.choice([0.0, 0.5]), 1)
    out_path = f"reports/memo_{topic.split()[0].lower()}.md"
    unit = {
        "id": "research_" + topic.split()[0].lower(),
        "family": "research_memo",
        "title": f"Research memo: {topic}",
        "brief": f"Write a short research memo on {topic}. Read the docs in the data source, "
                 f"then write {out_path} covering: (1) market size and CAGR, (2) the top region, "
                 f"(3) one key risk, (4) the current quote of ticker WRE.",
        "background": "The client needs this before the 11:00 review meeting.",
        "tools": ["dsv", "fs"],
        "verifier": {
            "type": "composite",
            "config": {
                "children": [
                    {"type": "file_created", "config": {"path": f"fs/{out_path}"}},
                    {"type": "file_contains", "config": {"path": f"fs/{out_path}",
                                                         "patterns": [r"CAGR", r"18", r"North America", r"regulation", r"WRE"]}},
                ]
            },
        },
        "checkpoints": [
            {"type": "file_created", "config": {"path": f"fs/{out_path}"}, "id": "cp_memo_created"},
            {"type": "file_contains", "config": {"path": f"fs/{out_path}", "patterns": [r"18", r"North America"]}, "id": "cp_memo_draft"},
        ],
        "priority": 4, "time_budget_min": 25, "rarity": 1, "interruptible": True,
        "produce_artifacts": [f"fs/{out_path}"],
    }
    world = {"dsv": {"kind": "dsv", "state": {"docs": {doc_market["name"]: doc_market["text"], doc_notes["name"]: doc_notes["text"]},
                                              "market": tickers}}}
    return unit, world


# --------------------------------------------------------------------------
# family: data_munging
# --------------------------------------------------------------------------

def gen_data_munging(rng: random.Random, ctx: dict):
    n = rng.randint(6, 9)
    base = 100
    rows = []
    for i in range(n):
        qty = base + i * 10 + rng.randint(0, 5)
        price = round(3.0 + rng.random() * 2, 2)
        rows.append([f"item{i}", qty, price, "kg", "USD"])
    rows.append([f"item{n}", base * 2, 4.1, "lb", "USD"])  # unit drift row
    dup = rows[1][:]
    dup[0] = "item1b"  # near-duplicate id
    rows.append(dup)
    table = {"cols": ["id", "qty", "price", "unit", "currency"], "rows": rows}
    out_path = "data/cleaned_inventory.csv"
    expected_rows = n  # agent must drop the lb row and the duplicate
    unit = {
        "id": "munging_inventory", "family": "data_munging",
        "title": "Clean the inventory CSV",
        "brief": f"The inventory table has unit drift (one row in lb) and a near-duplicate id. "
                 f"Write {out_path} with the same columns, only rows in kg/USD, "
                 f"duplicate id resolved by summing quantities, and qty rounded to integers. "
                 f"The file should have {expected_rows} data rows exactly.",
        "background": "Finance needs this for the budget model; they will read the file directly.",
        "tools": ["dsv", "fs"],
        "verifier": {
            "type": "composite",
            "config": {"children": [
                {"type": "csv_rows_match", "config": {"path": f"fs/{out_path}",
                                                      "must_include_rows": [{"id": "item0"}],
                                                      "total_rows_expected": expected_rows}},
                {"type": "numeric_assert", "config": {"path": f"fs/{out_path}",
                                                      "rows": [{"col": "qty", "op": "gt", "value": 0}]}},
            ]},
        },
        "checkpoints": [
            {"type": "file_created", "config": {"path": f"fs/{out_path}"}, "id": "cp_csv_created"},
        ],
        "priority": 3, "time_budget_min": 20, "rarity": 1, "interruptible": True,
        "produce_artifacts": [f"fs/{out_path}"],
    }
    world = {"dsv": {"kind": "dsv", "state": {"tables": {"inventory": table}}}}
    return unit, world


# --------------------------------------------------------------------------
# family: scheduling
# --------------------------------------------------------------------------

def gen_scheduling(rng: random.Random, ctx: dict):
    day = rng.choice(["Monday", "Tuesday", "Wednesday"])
    slot = rng.choice(["10:00", "14:00", "16:30"])
    person = rng.choice(NAMES)
    existing = [{"start": "09:00", "end": "09:45", "title": "Standup"},
                {"start": "13:00", "end": "13:30", "title": "Lunch"}]
    unit = {
        "id": "sched_review", "family": "scheduling",
        "title": f"Book the {day} review",
        "brief": f"Book a 60-minute review with {person} on {day} at {slot} (no email needed, "
                 f"just the calendar entry titled 'Project review with {person}'). "
                 f"It must not overlap the existing events.",
        "background": "Start/end are exact; keep the calendar conflict-free.",
        "tools": ["calendar"],
        "verifier": {"type": "calendar_invariant", "config": {
            "no_overlap": True,
            "requires_events": [{"start": slot, "end": f"{int(slot.split(':')[0]) + 1:02d}:00", "title_sub": person}],
        }},
        "checkpoints": [{"type": "calendar_invariant", "config": {"no_overlap": False, "requires_events": []}, "id": "cp_cal"}],
        "priority": 2, "time_budget_min": 5, "rarity": 1, "interruptible": True,
        "produce_artifacts": ["calendar/events"],
    }
    world = {"calendar": {"kind": "calendar", "state": {"owner": "me", "events": existing}}}
    return unit, world


# --------------------------------------------------------------------------
# family: comms
# --------------------------------------------------------------------------

def gen_comms(rng: random.Random, ctx: dict):
    person = rng.choice(NAMES)
    topic = rng.choice(["the memo", "the inventory file", "the updated itinerary"])
    attach = rng.choice(["memo_supply.md", "cleaned_inventory.csv"])
    unit = {
        "id": "comms_update", "family": "comms",
        "title": f"Email {person}",
        "brief": f"Send an email to {person}@corp.example updating them on {topic}. "
                 f"Subject must contain 'update'. Body: one-paragraph summary, mention the "
                 f"deliverable, and attach {attach}. Keep tone professional and under 120 words.",
        "background": "They are waiting on this before their standup.",
        "tools": ["email"],
        "verifier": {"type": "email_checks", "config": {"requires": [
            {"to": f"{person}@corp.example", "subject_sub": "update", "body_sub": "deliverable",
             "attach_sub": attach},
        ]}},
        "checkpoints": [],
        "priority": 2, "time_budget_min": 10, "rarity": 1, "interruptible": True,
        "produce_artifacts": ["email/sent"],
    }
    world = {"email": {"kind": "email", "state": {"sent": [], "inbox": [{"from": "ops@corp.example", "subject": "CI failing", "body": "build 42 red"}]}}}
    return unit, world


# --------------------------------------------------------------------------
# family: code_fix
# --------------------------------------------------------------------------

def gen_code_fix(rng: random.Random, ctx: dict):
    buggy = (
        "def parse_orders(text):\n"
        "    lines = [l for l in text.strip().splitlines() if l.strip()]\n"
        "    out = []\n"
        "    for l in lines[1:]:\n"
        "        parts = l.split(',')\n"
        "        out.append((parts[0], int(parts[1])))  # BUG: qty may be '12 units'\n"
        "    return out\n"
        "\n"
        "def total(text):\n"
        "    return sum(q for _, q in parse_orders(text))\n"
    )
    hidden_tests = (
        "import re\n"
        "def _num(x): return int(re.sub(r'[^0-9]', '', x))\n"
        "test_text = 'sku,qty\\nA1,\\'12 units\\'\\nB2,7\\nC3,\\'5 units\\''\n"
        "assert total(test_text) == 24, total(test_text)\n"
        "test_text2 = 'sku,qty\\nX1,\\'0 units\\'\\nY2,3'\n"
        "assert total(test_text2) == 3, total(test_text2)\n"
        "print('ALL_TESTS_PASSED')\n"
    )
    unit = {
        "id": "codefix_orders", "family": "code_fix",
        "title": "Fix parse_orders bug",
        "brief": "The orders parser crashes on quantities like '12 units'. Fix parse_orders "
                 "in code repo file orders.py so total() sums numeric parts only. "
                 "Do not change total(). Hidden tests will verify.",
        "background": "CI is red; the fix should stay minimal.",
        "tools": ["code"],
        "verifier": {"type": "code_passes", "config": {
            "file": "code/orders.py", "hidden_tests": hidden_tests, "marker": "ALL_TESTS_PASSED", "timeout_s": 15,
        }},
        "checkpoints": [{"type": "file_created", "config": {"path": "code/orders.py"}, "id": "cp_code"}],
        "priority": 5, "time_budget_min": 30, "rarity": 2, "interruptible": True,
        "produce_artifacts": ["code/orders.py"],
    }
    world = {"code": {"kind": "code", "state": {"files": {"orders.py": buggy}, "readme": "tiny repo"}}}
    return unit, world


# --------------------------------------------------------------------------
# family: math_word
# --------------------------------------------------------------------------

def gen_math_word(rng: random.Random, ctx: dict):
    a = rng.randint(40, 120)
    b = rng.randint(2, 6)
    c = rng.randint(3, 9)
    ans = a * b + c
    unit = {
        "id": "math_profit", "family": "math_word",
        "title": "Profit math",
        "brief": f"Each unit sells at {a} CNY net; we ship {b} units per day; fixed overhead is {c} x 10 CNY "
                 f"per day. Reply with the daily net profit as a single number (do the arithmetic, "
                 f"answer in your final reply as 'Answer: <number>').",
        "background": "",
        "tools": [],
        "verifier": {"type": "numeric_assert", "config": {"source": "reply",
                                                          "rows": [{"op": "eq", "value": ans, "tol": 0.5}]}},
        "checkpoints": [],
        "priority": 1, "time_budget_min": 4, "rarity": 1, "interruptible": True,
    }
    return unit, {}


# --------------------------------------------------------------------------
# family: travel_plan
# --------------------------------------------------------------------------

def gen_travel_plan(rng: random.Random, ctx: dict):
    city = rng.choice(CITIES)
    budget = rng.choice([1500, 1800, 2200])
    must = rng.sample(["convention center visit", "local dinner", "factory tour"], 2)
    out_path = "travel/itinerary.txt"
    unit = {
        "id": "travel_itinerary", "family": "travel_plan",
        "title": f"Build the {city} itinerary",
        "brief": f"Plan a one-day business itinerary for {city}: write {out_path} containing "
                 f"a day plan starting with 'Morning', including {must[0]} and {must[1]} in that order, "
                 f"a 'Budget' line whose total $ amount does not exceed {budget}, and mention the "
                 f"hotel district (any choice).",
        "background": "The ops team executes whatever is in the file, verbatim.",
        "tools": ["fs"],
        "verifier": {"type": "constraint_solver", "config": {
            "path": f"fs/{out_path}",
            "must_include": [city, "Morning", "Budget"],
            "order": [must[0], must[1]],
            "budget_cap": budget,
        }},
        "checkpoints": [{"type": "file_created", "config": {"path": f"fs/{out_path}"}, "id": "cp_travel"}],
        "priority": 3, "time_budget_min": 15, "rarity": 2, "interruptible": True,
        "produce_artifacts": [f"fs/{out_path}"],
    }
    return unit, {}


# --------------------------------------------------------------------------
# family: creative_brief
# --------------------------------------------------------------------------

def gen_creative_brief(rng: random.Random, ctx: dict):
    product = rng.choice(["cold-brew energy cans", "calm-focus desk lamp", "modular power bank"])
    out_path = "briefs/launch_brief.txt"
    unit = {
        "id": "brief_launch", "family": "creative_brief",
        "title": "Write the launch brief",
        "brief": f"Write a one-page launch brief for {product}. Save it to {out_path}. "
                 f"It must contain a headline, a 'Target audience' section, a 'Messaging' section "
                 f"and 3 bullet points. At least 80 words. No placeholder text like 'TODO' or 'TBD'.",
        "background": "The designer needs this by EOD; quality matters more than length.",
        "tools": ["fs"],
        "verifier": {"type": "keyword_structure", "config": {
            "path": f"fs/{out_path}",
            "must_include": ["headline", "Target audience", "Messaging"],
            "must_not_include": ["TODO", "TBD"],
            "min_words": 80,
            "structure_order": ["Target audience", "Messaging"],
        }},
        "checkpoints": [{"type": "file_created", "config": {"path": f"fs/{out_path}"}, "id": "cp_brief"}],
        "priority": 2, "time_budget_min": 20, "rarity": 3, "interruptible": True,
        "produce_artifacts": [f"fs/{out_path}"],
    }
    return unit, {}


# --------------------------------------------------------------------------
# exotic / long-tail families (novelty tiers 3-4)
# --------------------------------------------------------------------------

def gen_legal_clause(rng: random.Random, ctx: dict):
    """Long-tail: contract skimming — not in the head distribution."""
    out_path = "legal/clause_check.txt"
    unit = {
        "id": "legal_clause", "family": "legal_clause",
        "title": "Flag contract clause",
        "brief": f"Read the contract draft in the data source (doc 'contract.md'), find the clause "
                 f"with 'autorenew', and write {out_path} with one line: the clause number "
                 f"and a one-line plain-language summary. Nothing else.",
        "background": "",
        "tools": ["dsv", "fs"],
        "verifier": {"type": "file_contains", "config": {
            "path": f"fs/{out_path}", "patterns": [r"autorenew", r"\d", r"renew"]}},
        "checkpoints": [],
        "priority": 3, "time_budget_min": 12, "rarity": 4, "interruptible": True,
        "produce_artifacts": [f"fs/{out_path}"],
    }
    world = {"dsv": {"kind": "dsv", "state": {"docs": {"contract.md": (
        "AGREEMENT v7\nClause 3.2: Either party may terminate with 30 days notice.\n"
        "Clause 4.1: This agreement shall autorenew annually unless a written notice is provided "
        "at least 60 days before renewal. Notice must reference this clause.\n"
        "Clause 5.0: Law: Singapore."
    )}}}}
    return unit, world


def gen_quiz(rng: random.Random, ctx: dict):
    """Long-tail: trivia with a strict format contract."""
    q = rng.choice([("capital of Chile", "Santiago"), ("largest moon of Saturn", "Titan"),
                    ("year of the first Moon landing", "1969")])
    unit = {
        "id": "quiz_q", "family": "quiz",
        "title": "One-line answer",
        "brief": f"What is the {q[0]}? Reply in the final message, format exactly: `Answer: ...`",
        "background": "",
        "tools": [],
        "verifier": {"type": "keyword_structure", "config": {
            "source": "reply", "must_include": [q[1]], "must_not_include": ["Answer: Answer"]}},
        "checkpoints": [],
        "priority": 1, "time_budget_min": 2, "rarity": 4, "interruptible": True,
    }
    return unit, {}


FAMILIES = {
    "research_memo": gen_research_memo,
    "data_munging": gen_data_munging,
    "scheduling": gen_scheduling,
    "comms": gen_comms,
    "code_fix": gen_code_fix,
    "math_word": gen_math_word,
    "travel_plan": gen_travel_plan,
    "creative_brief": gen_creative_brief,
    "legal_clause": gen_legal_clause,
    "quiz": gen_quiz,
}

# Head vs tail weight (rarity tiers): head families are frequent, tail families rare.
RARITY_TO_FAMILIES = {1: ["research_memo", "data_munging", "scheduling", "comms", "math_word"],
                      2: ["code_fix", "travel_plan"],
                      3: ["creative_brief"],
                      4: ["legal_clause", "quiz"]}


def sample_family(rng: random.Random, rarity: int) -> str:
    fams = RARITY_TO_FAMILIES.get(rarity, RARITY_TO_FAMILIES[1])
    return rng.choice(fams)


def generate_unit(rng: random.Random, rarity: int, unit_idx: int) -> tuple[dict, dict]:
    family = sample_family(rng, rarity)
    unit, world = FAMILIES[family](rng, {"rarity": rarity, "idx": unit_idx})
    unit["rarity"] = rarity
    unit["id"] = f"t{unit_idx:02d}_{unit['id']}"
    return unit, world