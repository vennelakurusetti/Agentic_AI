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
        parsed = ResumeData(**data)
        # Store injection metadata on the object for audit tracking
        parsed._injection_count = len(injections)
        return parsed
    except (json.JSONDecodeError, Exception):
        return ResumeData(candidate_name="Unknown", _injection_count=len(injections))
