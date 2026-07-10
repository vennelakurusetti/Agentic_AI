PARSER_PROMPT = """You are an expert resume parser.

Extract structured information.

Return JSON.

{{
"name":"",
"education":[],
"experience_years":0,
"skills":[],
"projects":[],
"certifications":[],
"communication_evidence":"",
"resume_lines":[]
}}

Rules

Do not summarize.

Do not judge.

Extract facts only.

Keep exact wording whenever possible.

Resume

{resume_text}
"""
