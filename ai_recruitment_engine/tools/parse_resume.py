import json
from tools.sanitizer import sanitize, SafePromptWrapper, contains_injection
from prompts.parser_prompt import PARSER_PROMPT
from models.schemas import ResumeData

def parse_resume(resume_text: str, llm_call) -> ResumeData:
    """
    Parse resume text into structured ResumeData using LLM.
    
    SECURITY: resume_text is UNTRUSTED. It is sanitized before processing
    to remove prompt injection attempts.
    """
    # Step 1: Sanitize - strip injection lines from resume text
    clean_text = sanitize(resume_text)
    
    # Step 2: Check for injections (for audit logging)
    injections = contains_injection(resume_text)
    if injections:
        # Log warning (caller can access via return metadata if needed)
        pass  # Injection detected and removed
    
    # Step 3: Build the parsing prompt with security wrapper
    raw_prompt = PARSER_PROMPT.format(resume_text=clean_text)
    safe_prompt = SafePromptWrapper.wrap_resume_parsing(raw_prompt)
    
    # Step 4: Call LLM with secured prompt
    response = llm_call(safe_prompt)
    
    try:
        data = json.loads(response)
        # Map 'name' from parser output to 'candidate_name' in our model
        if "name" in data:
            data["candidate_name"] = data.pop("name")
        
        # Normalize education: LLM may return list of objects or list of strings
        if "education" in data and isinstance(data["education"], list):
            edu_strings = []
            for e in data["education"]:
                if isinstance(e, dict):
                    parts = [str(v) for v in [e.get("degree",""), e.get("field",""), e.get("institution","")] if v]
                    cgpa = e.get("cgpa")
                    if cgpa:
                        parts.append(f"(CGPA: {cgpa})")
                    edu_strings.append(" ".join(parts) if parts else str(e))
                else:
                    edu_strings.append(str(e))
            data["education"] = edu_strings
        
        # Normalize projects: LLM may return list of objects or list of strings
        if "projects" in data and isinstance(data["projects"], list):
            proj_strings = []
            for p in data["projects"]:
                if isinstance(p, dict):
                    title = p.get("title", "")
                    desc = p.get("description", "")
                    proj_strings.append(f"{title}: {desc}" if title and desc else (title or desc or str(p)))
                else:
                    proj_strings.append(str(p))
            data["projects"] = proj_strings
        
        # Normalize experience_years: LLM may return 0 for freshers
        if "experience_years" in data and data["experience_years"] is None:
            data["experience_years"] = 0
        
        parsed = ResumeData(**data)
        # Store injection metadata on the object for audit tracking
        parsed._injection_count = len(injections)
        return parsed
    except (json.JSONDecodeError, Exception) as e:
        print(f"[WARN] Resume parse failed: {e}")
        return ResumeData(candidate_name="Unknown", _injection_count=len(injections))
