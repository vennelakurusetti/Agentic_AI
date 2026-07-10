RUBRIC_PROMPT = """You are a Senior Technical Recruiter.

Given the extracted job requirements, create an objective hiring rubric.

Each criterion must contain:
- criterion name
- weight (total must sum to 100)
- description
- score scale (0-5) with level descriptions
- what counts as evidence

Return ONLY JSON with this structure:
{{
  "criteria": [
    {{
      "name": "Python",
      "weight": 30,
      "description": "Proficiency in Python programming",
      "evidence": "Projects or work using Python",
      "levels": {{
        "0": "No Python experience",
        "1": "Basic syntax knowledge",
        "2": "Small scripts or projects",
        "3": "Academic or internship projects",
        "4": "Strong practical use in production",
        "5": "Professional-level proficiency, expert"
      }}
    }}
  ]
}}

RULES:
- Total weight across all criteria MUST equal exactly 100.
- Include criteria for ALL required skills, education, experience, and communication.
- Preferred skills should be grouped or weighted lower.
- Be objective and measurable in level descriptions.
- Output valid JSON only.

EXTRACTED JOB REQUIREMENTS:
{jd_parsed}

RAW JOB DESCRIPTION (for additional context):
{jd_raw}
"""