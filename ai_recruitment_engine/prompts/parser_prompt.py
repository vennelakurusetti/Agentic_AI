PARSER_PROMPT = """You are an expert resume parser.

Extract structured information from the resume text below.

Return ONLY valid JSON (no markdown, no code fences):

{{
  "name": "",
  "education": [],
  "experience_years": 0,
  "experience_details": [],
  "skills": [],
  "projects": [],
  "certifications": [],
  "communication_evidence": "",
  "resume_lines": []
}}

Field rules:
- name: full candidate name exactly as written
- education: list of strings, each entry = "Degree Field Institution (CGPA if present)"
- experience_years: integer total years of professional work experience (0 for students/freshers)
- experience_details: list of strings, each entry = one job role + key responsibilities (e.g. "SWE at Acme Corp: built REST APIs with Python, managed 5-person team")
- skills: flat list of individual skill strings (e.g. ["Python", "React", "AWS"])
- projects: list of strings, each = "Project Title: brief description"
- certifications: list of certification names
- communication_evidence: one sentence summarising any evidence of communication/leadership skills
- resume_lines: verbatim copy of up to 20 key lines from the resume for reference

Rules:
- Do not summarize or judge — extract facts only.
- Keep exact wording wherever possible.
- Do not hallucinate data not present in the resume.

Resume:
{resume_text}
"""
