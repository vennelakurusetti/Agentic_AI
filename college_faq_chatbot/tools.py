"""
tools.py -- Function calling tools for the College FAQ Chatbot.

Validations applied:
  - fee_calculator: rejects contradictory branch names
  - date_checker: rejects empty/invalid event names; auto-computes days remaining
  - percentage_calculator: rejects negative marks, negative total, marks > total,
    negative scholarship %, scholarship > 100%
"""

import re
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple

from utils import logger

# ---------------------------------------------------------------------------
# 1. TOOL DESCRIPTIONS
# ---------------------------------------------------------------------------

TOOL_DESCRIPTIONS = {
    "fee_calculator": (
        "Use this tool when the user asks about fees, fee structure, tuition cost, "
        "total fees, annual fees, or how much it costs to study at BVRIT Hyderabad. "
        "Input: branch name (optional) and category (general/management/NRI)."
    ),
    "date_checker": (
        "Use this tool when the user asks about important dates, deadlines, "
        "admission open/close dates, exam schedules, last date to apply, "
        "days remaining until a deadline, or whether a deadline has passed. "
        "Input: event or topic name."
    ),
    "percentage_calculator": (
        "Use this tool when the user wants to calculate their percentage from marks, "
        "check eligibility based on score, or convert marks to percentage. "
        "Input: marks obtained and total marks."
    ),
}

# ---------------------------------------------------------------------------
# 2. FEE DATA
# ---------------------------------------------------------------------------

FEE_STRUCTURE: Dict[str, Dict[str, Any]] = {
    "cse":   {"full_name": "Computer Science Engineering (CSE)",                   "general": 115000, "management": 200000, "nri": 350000, "hostel": 85000, "transport": 15000, "notes": "Fees are per annum. Hostel and transport are optional."},
    "ece":   {"full_name": "Electronics and Communication Engineering (ECE)",      "general": 110000, "management": 195000, "nri": 340000, "hostel": 85000, "transport": 15000, "notes": "Fees are per annum. Hostel and transport are optional."},
    "eee":   {"full_name": "Electrical and Electronics Engineering (EEE)",         "general": 105000, "management": 185000, "nri": 330000, "hostel": 85000, "transport": 15000, "notes": "Fees are per annum. Hostel and transport are optional."},
    "it":    {"full_name": "Information Technology (IT)",                          "general": 112000, "management": 198000, "nri": 345000, "hostel": 85000, "transport": 15000, "notes": "Fees are per annum. Hostel and transport are optional."},
    "mech":  {"full_name": "Mechanical Engineering",                               "general": 100000, "management": 175000, "nri": 310000, "hostel": 85000, "transport": 15000, "notes": "Fees are per annum. Hostel and transport are optional."},
    "civil": {"full_name": "Civil Engineering",                                    "general":  95000, "management": 170000, "nri": 300000, "hostel": 85000, "transport": 15000, "notes": "Fees are per annum. Hostel and transport are optional."},
    "aiml":  {"full_name": "Artificial Intelligence and Machine Learning (AI&ML)", "general": 120000, "management": 210000, "nri": 360000, "hostel": 85000, "transport": 15000, "notes": "Fees are per annum. Hostel and transport are optional."},
    "ds":    {"full_name": "Data Science (DS)",                                    "general": 118000, "management": 205000, "nri": 355000, "hostel": 85000, "transport": 15000, "notes": "Fees are per annum. Hostel and transport are optional."},
    "default":{"full_name": "B.Tech (General)",                                   "general": 110000, "management": 195000, "nri": 340000, "hostel": 85000, "transport": 15000, "notes": "Approximate fees. Contact admissions for exact figures."},
}

BRANCH_ALIASES: Dict[str, str] = {
    "computer science": "cse", "computer science engineering": "cse",
    "computers": "cse", "cs": "cse", "cse": "cse",
    "electronics": "ece", "electronics and communication": "ece", "ece": "ece",
    "electrical": "eee", "electrical and electronics": "eee", "eee": "eee",
    "information technology": "it", "it": "it",
    "mechanical": "mech", "mechanical engineering": "mech", "mech": "mech",
    "civil": "civil", "civil engineering": "civil",
    "ai": "aiml", "aiml": "aiml", "ai&ml": "aiml",
    "artificial intelligence": "aiml", "machine learning": "aiml",
    "ai and ml": "aiml", "ai ml": "aiml",
    "data science": "ds", "ds": "ds",
}

# Contradictory branch pairs that cannot be the same branch
_CONTRADICTORY_BRANCH_PAIRS: List[Tuple[str, str]] = [
    ("cse", "civil"), ("ece", "civil"), ("cse", "mech"),
    ("aiml", "civil"), ("ds", "civil"), ("eee", "aiml"),
]

# ---------------------------------------------------------------------------
# 3. DATE DATA
# ---------------------------------------------------------------------------

IMPORTANT_DATES: Dict[str, Dict[str, Any]] = {
    "ts_eamcet": {
        "name": "TS EAMCET / TS EAPCET",
        "exam_date": "May 2026 (exact dates announced by TSCHE)",
        "application_start": "February 2026",
        "application_deadline": "April 2026",
        "hall_ticket": "May 2026",
        "results": "June 2026",
        "counseling": "June-July 2026",
        "notes": "Dates are approximate. Visit https://tsche.ac.in for official schedule.",
        "deadline_date": "2026-04-30",
        "deadline_label": "Application Deadline",
    },
    "admission": {
        "name": "BVRIT Hyderabad Admissions",
        "application_open": "April 2026",
        "application_deadline": "July 2026",
        "counseling_rounds": "July-August 2026",
        "classes_start": "August 2026",
        "notes": "Management quota seats available after EAMCET counseling. Contact: admissions@bvrithyderabad.edu.in",
        "deadline_date": "2026-07-31",
        "deadline_label": "Application Deadline",
    },
    "academic_calendar": {
        "name": "Academic Calendar 2025-26",
        "semester_1_start": "August 2025",
        "semester_1_end": "December 2025",
        "semester_1_exams": "November-December 2025",
        "semester_2_start": "January 2026",
        "semester_2_end": "May 2026",
        "semester_2_exams": "April-May 2026",
        "summer_break": "May-July 2026",
        "notes": "Subject to revision. Check college website for updates.",
        "deadline_date": "2026-05-31",
        "deadline_label": "Semester 2 End",
    },
    "internship": {
        "name": "Internship Season",
        "summer_internship": "May-July 2026",
        "placement_season_start": "August 2026",
        "on_campus_drives": "September 2026 onwards",
        "notes": "Pre-placement offers (PPOs) typically issued by October.",
        "deadline_date": "2026-08-01",
        "deadline_label": "Placement Season Start",
    },
    "fees_payment": {
        "name": "Fee Payment Deadlines",
        "semester_1_deadline": "August 15, 2025",
        "semester_2_deadline": "January 15, 2026",
        "late_fee_penalty": "Rs.500/week after deadline",
        "notes": "Online payment available at https://bvrithyderabad.edu.in/fees",
        "deadline_date": "2026-01-15",
        "deadline_label": "Semester 2 Fee Deadline",
    },
    "hostel": {
        "name": "Hostel Admission",
        "application_open": "April 2026",
        "application_deadline": "July 2026",
        "allotment": "August 2026",
        "notes": "Limited seats. First-come-first-served basis.",
        "deadline_date": "2026-07-31",
        "deadline_label": "Hostel Application Deadline",
    },
}

DATE_ALIASES: Dict[str, str] = {
    "eamcet": "ts_eamcet", "eapcet": "ts_eamcet",
    "ts eamcet": "ts_eamcet", "ts eapcet": "ts_eamcet",
    "entrance exam": "ts_eamcet", "entrance": "ts_eamcet",
    "admission": "admission", "admissions": "admission",
    "apply": "admission", "application": "admission", "joining": "admission",
    "academic calendar": "academic_calendar", "calendar": "academic_calendar",
    "semester": "academic_calendar", "exam": "academic_calendar", "exams": "academic_calendar",
    "internship": "internship", "placement": "internship", "internships": "internship",
    "fee": "fees_payment", "fees": "fees_payment", "payment": "fees_payment",
    "hostel": "hostel", "accommodation": "hostel",
    "counseling": "admission", "counselling": "admission",
    "deadline": "admission", "last date": "admission",
}

ELIGIBILITY_CRITERIA = {
    "btech_general": 45.0,
    "btech_sc_st": 40.0,
    "btech_lateral_entry": 45.0,
    "management_quota": 40.0,
}

# ---------------------------------------------------------------------------
# 4. INPUT SANITIZATION
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS = re.compile(
    r"(ignore|system\s*prompt|admin|password|hack|override|pretend|"
    r"you\s*are\s*now|instruction|jailbreak|<script|eval\(|exec\()",
    re.IGNORECASE,
)


def sanitize_input(value: str, field_name: str = "input") -> str:
    if not isinstance(value, str):
        raise ValueError(f"Tool {field_name} must be a string, got {type(value).__name__}")
    value = value.strip()
    if len(value) > 200:
        value = value[:200]
    if _INJECTION_PATTERNS.search(value):
        logger.warning(f"Possible injection attempt in tool {field_name}: {value[:50]}")
        raise ValueError(f"Invalid {field_name}: contains disallowed content")
    return value


def normalize_branch(branch: str) -> str:
    cleaned = branch.lower().strip()
    if cleaned in BRANCH_ALIASES:
        return BRANCH_ALIASES[cleaned]
    for alias, key in BRANCH_ALIASES.items():
        if alias in cleaned or cleaned in alias:
            return key
    return "default"


def normalize_event(event: str) -> str:
    cleaned = event.lower().strip()
    if cleaned in DATE_ALIASES:
        return DATE_ALIASES[cleaned]
    for alias, key in DATE_ALIASES.items():
        if alias in cleaned or cleaned in alias:
            return key
    return "admission"


def _days_until(deadline_str: str) -> Tuple[int, bool]:
    """
    Given a YYYY-MM-DD string, return (days, is_future).
    days > 0  -> deadline is in the future
    days == 0 -> deadline is today
    days < 0  -> deadline has already passed
    """
    try:
        deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
        today = date.today()
        delta = (deadline - today).days
        return delta, delta >= 0
    except ValueError:
        return 0, True


# ---------------------------------------------------------------------------
# 5. THE THREE TOOLS
# ---------------------------------------------------------------------------

def fee_calculator(branch: str = "general", category: str = "general") -> Dict[str, Any]:
    """Return fee structure for a given branch and admission category."""
    try:
        branch = sanitize_input(branch, "branch")
        category = sanitize_input(category, "category")
    except ValueError as e:
        return {
            "tool_name": "fee_calculator",
            "error": str(e),
            "answer": "I could not process that input. Please provide a valid branch name.",
            "citations": [],
        }

    # Validate: reject clearly contradictory branch names
    lower_branch = branch.lower().strip()
    detected_keys = [key for alias, key in BRANCH_ALIASES.items() if alias in lower_branch]
    unique_keys = list(dict.fromkeys(detected_keys))
    if len(unique_keys) >= 2:
        pair = tuple(sorted(unique_keys[:2]))
        if pair in [tuple(sorted(p)) for p in _CONTRADICTORY_BRANCH_PAIRS]:
            return {
                "tool_name": "fee_calculator",
                "error": "Contradictory branch names provided.",
                "answer": (
                    f"I noticed conflicting branch names in your query "
                    f"('{unique_keys[0].upper()}' and '{unique_keys[1].upper()}'). "
                    "Please specify a single branch so I can give you the correct fee structure."
                ),
                "citations": [],
            }

    # Validate category
    cat_clean = category.lower().strip()
    if cat_clean not in {"general", "management", "nri"}:
        if "mgmt" in cat_clean:
            cat_clean = "management"
        elif "nri" in cat_clean or "foreign" in cat_clean:
            cat_clean = "nri"
        else:
            cat_clean = "general"

    branch_key = normalize_branch(branch)
    fee_data = FEE_STRUCTURE.get(branch_key, FEE_STRUCTURE["default"])
    annual_fee = fee_data.get(cat_clean, fee_data["general"])
    total_4yr = annual_fee * 4

    answer = (
        f"**Fee Structure for {fee_data['full_name']} ({cat_clean.title()} Category)**\n\n"
        f"- Annual Tuition Fee: Rs.{annual_fee:,}\n"
        f"- Total (4 Years): Rs.{total_4yr:,}\n"
        f"- Hostel Charges: Rs.{fee_data['hostel']:,}/year (optional)\n"
        f"- Transport: Rs.{fee_data['transport']:,}/year (optional)\n\n"
        f"*{fee_data['notes']}*\n\n"
        "For exact and official fee details, contact the admissions office or visit "
        "https://bvrithyderabad.edu.in"
    )
    logger.info(f"fee_calculator: branch={branch_key}, category={cat_clean}, fee={annual_fee}")
    return {
        "tool_name": "fee_calculator",
        "branch": fee_data["full_name"],
        "category": cat_clean,
        "annual_fee": annual_fee,
        "total_4_year": total_4yr,
        "hostel_fee": fee_data["hostel"],
        "transport_fee": fee_data["transport"],
        "answer": answer,
        "citations": ["Fee Structure", "Admissions"],
    }


def date_checker(event_name: str = "admission", compute_days: bool = True) -> Dict[str, Any]:
    """
    Return important dates for a college event.
    Automatically computes days remaining until / days since the deadline.

    Always uses compute_days=True (default) so deadline proximity is always shown.
    """
    try:
        event_name = sanitize_input(event_name, "event_name")
    except ValueError as e:
        return {
            "tool_name": "date_checker",
            "error": str(e),
            "answer": "I could not process that input. Please specify a valid event name such as 'admission', 'eamcet', or 'hostel'.",
            "citations": [],
        }

    if not event_name.strip():
        return {
            "tool_name": "date_checker",
            "error": "Event name cannot be empty.",
            "answer": "Please specify which event you want dates for (e.g., admission, EAMCET, hostel).",
            "citations": [],
        }

    event_key = normalize_event(event_name)
    date_data = IMPORTANT_DATES.get(event_key, IMPORTANT_DATES["admission"])

    # Build readable date list
    skip_keys = {"name", "notes", "deadline_date", "deadline_label"}
    lines = [f"**{date_data['name']} -- Important Dates**\n"]
    for key, value in date_data.items():
        if key in skip_keys:
            continue
        label = key.replace("_", " ").title()
        lines.append(f"- {label}: {value}")

    # Compute remaining / elapsed days (always computed)
    days_line = ""
    if date_data.get("deadline_date"):
        days, is_future = _days_until(date_data["deadline_date"])
        label = date_data.get("deadline_label", "Deadline")
        today_str = date.today().strftime("%B %d, %Y")
        if is_future and days > 0:
            days_line = (
                f"\n**Days Remaining until {label}:** {days} days "
                f"(as of {today_str})"
            )
        elif days == 0:
            days_line = f"\n**{label} is TODAY** ({today_str})"
        else:
            days_line = (
                f"\n**{label} has passed** -- it was {abs(days)} days ago "
                f"(as of {today_str}). Please check the official website for updated dates."
            )

    if date_data.get("notes"):
        lines.append(f"\n*{date_data['notes']}*")
    if days_line:
        lines.append(days_line)

    answer = "\n".join(lines)
    logger.info(f"date_checker: event={event_key}, days={_days_until(date_data.get('deadline_date',''))[0] if date_data.get('deadline_date') else 'N/A'}")
    return {
        "tool_name": "date_checker",
        "event": date_data["name"],
        "dates": {k: v for k, v in date_data.items() if k not in skip_keys},
        "days_until_deadline": (
            _days_until(date_data["deadline_date"])[0]
            if date_data.get("deadline_date") else None
        ),
        "answer": answer,
        "citations": ["Academic Calendar", "Admissions"],
    }


def percentage_calculator(marks: Any, total: Any, category: str = "general") -> Dict[str, Any]:
    """
    Calculate percentage from marks and check B.Tech eligibility.

    Validations:
    - Marks must be a non-negative number
    - Total must be > 0
    - Marks cannot exceed total
    - Scholarship percentage (if pre-computed) cannot be negative or > 100
    """
    # Numeric type conversion and validation
    try:
        marks_val = float(marks)
        total_val = float(total)
    except (ValueError, TypeError):
        return {
            "tool_name": "percentage_calculator",
            "error": "Marks and total must be numbers.",
            "answer": "Please provide valid numeric values for marks and total marks. Example: '450 out of 600'.",
            "citations": [],
        }

    # Negative marks check
    if marks_val < 0:
        return {
            "tool_name": "percentage_calculator",
            "error": "Marks cannot be negative.",
            "answer": (
                f"Invalid input: marks cannot be negative (you entered {marks_val:.0f}). "
                "Please provide your actual marks obtained."
            ),
            "citations": [],
        }

    # Zero or negative total check
    if total_val <= 0:
        return {
            "tool_name": "percentage_calculator",
            "error": "Total marks must be greater than 0.",
            "answer": (
                f"Invalid input: total marks must be greater than zero (you entered {total_val:.0f}). "
                "Please provide the maximum possible marks."
            ),
            "citations": [],
        }

    # Marks exceeds total check
    if marks_val > total_val:
        return {
            "tool_name": "percentage_calculator",
            "error": "Marks cannot exceed total marks.",
            "answer": (
                f"Invalid input: marks obtained ({marks_val:.0f}) cannot be greater than "
                f"total marks ({total_val:.0f}). Please check your values."
            ),
            "citations": [],
        }

    # Sanitize category
    try:
        category = sanitize_input(str(category), "category")
    except ValueError:
        category = "general"

    percentage = round((marks_val / total_val) * 100, 2)

    # Scholarship pre-computed percentage validation
    # (If someone passes percentage directly as marks with total=100)
    if total_val == 100:
        if percentage < 0:
            return {
                "tool_name": "percentage_calculator",
                "error": "Scholarship percentage cannot be negative.",
                "answer": "Scholarship percentage cannot be negative. Please enter a value between 0 and 100.",
                "citations": [],
            }
        if percentage > 100:
            return {
                "tool_name": "percentage_calculator",
                "error": "Scholarship percentage cannot exceed 100%.",
                "answer": (
                    f"Scholarship percentage cannot exceed 100% (you entered {percentage:.1f}%). "
                    "Please check your input."
                ),
                "citations": [],
            }

    # Category detection
    cat_clean = category.lower().strip()
    if "sc" in cat_clean or "st" in cat_clean:
        threshold = ELIGIBILITY_CRITERIA["btech_sc_st"]
        cat_label = "SC/ST Category"
    elif "management" in cat_clean or "mgmt" in cat_clean:
        threshold = ELIGIBILITY_CRITERIA["management_quota"]
        cat_label = "Management Quota"
    elif "lateral" in cat_clean or "diploma" in cat_clean:
        threshold = ELIGIBILITY_CRITERIA["btech_lateral_entry"]
        cat_label = "Lateral Entry"
    else:
        threshold = ELIGIBILITY_CRITERIA["btech_general"]
        cat_label = "General Category"

    eligible = percentage >= threshold
    eligibility_str = "ELIGIBLE" if eligible else "NOT ELIGIBLE"
    gap = round(threshold - percentage, 2) if not eligible else 0

    answer = (
        f"**Percentage Calculation Result**\n\n"
        f"- Marks Obtained: {marks_val:.0f} / {total_val:.0f}\n"
        f"- Percentage: **{percentage}%**\n"
        f"- B.Tech Eligibility ({cat_label}): **{eligibility_str}**\n"
        f"- Required Minimum: {threshold}%\n"
    )
    if not eligible:
        answer += f"- Shortfall: {gap}% below the minimum requirement\n"
    answer += (
        "\n*Eligibility is also subject to TS EAMCET rank, category certificates, "
        "and seat availability. Contact the admissions office for final confirmation.*"
    )

    logger.info(f"percentage_calculator: {marks_val}/{total_val} = {percentage}% eligible={eligible}")
    return {
        "tool_name": "percentage_calculator",
        "marks": marks_val,
        "total": total_val,
        "percentage": percentage,
        "eligible": eligible,
        "threshold": threshold,
        "category": cat_label,
        "answer": answer,
        "citations": ["Admissions", "Eligibility Criteria"],
    }


# ---------------------------------------------------------------------------
# 6. TOOL REGISTRY
# ---------------------------------------------------------------------------

TOOL_REGISTRY: Dict[str, Any] = {
    "fee_calculator": fee_calculator,
    "date_checker": date_checker,
    "percentage_calculator": percentage_calculator,
}


def get_tool(tool_name: str):
    return TOOL_REGISTRY.get(tool_name)


def list_tools() -> List[Dict[str, str]]:
    return [{"name": name, "description": desc} for name, desc in TOOL_DESCRIPTIONS.items()]
