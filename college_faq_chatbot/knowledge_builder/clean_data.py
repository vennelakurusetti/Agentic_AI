"""
clean_data.py - Clean extracted text by removing junk and keeping only meaningful content
"""

import re
import os

# Keywords to filter out (junk lines)
JUNK_KEYWORDS = [
    "search", "skip to content", "facebook", "instagram", "twitter",
    "linkedin", "youtube", "login", "menu", "home", "copyright",
    "privacy policy", "terms of use", "all rights reserved", "powered by",
    "scroll", "click here", "read more", "share this", "follow us",
    "subscribe", "newsletter", "cookie", "back to top", "page load",
    "loading", "error", "404", "not found", "toggle navigation",
    "quick links", "useful links", "related links", "social media",
    "craftedbyreinaphics", "reinaphics"
]

# Important sections to keep
IMPORTANT_SECTIONS = [
    "about", "vision", "mission", "department", "admission", "fee",
    "placement", "faculty", "contact", "facility", "library", "hostel",
    "transport", "sport", "club", "research", "publication", "patent",
    "nirf", "naac", "accreditation", "autonomous", "curriculum",
    "laboratory", "infrastructure", "scholarship", "internship",
    "training", "activity", "event", "achievement", "award",
    "committee", "council", "cell", "center", "centre"
]


def is_junk_line(line):
    """Check if a line is junk/unwanted content."""
    line_lower = line.lower().strip()
    
    # Skip very short lines
    if len(line_lower) < 3:
        return True
    
    # Skip lines containing junk keywords
    for keyword in JUNK_KEYWORDS:
        if keyword in line_lower:
            return True
    
    # Skip lines that are just numbers or special characters
    if re.match(r'^[\d\s\-–—|/\\()\[\]{}.,:;!?@#$%^&*+=\'\"]+$', line_lower):
        return True
    
    # Skip lines that are just single words (like navigation items)
    if len(line_lower.split()) <= 2 and len(line_lower) < 20:
        # But keep if it looks like a heading
        if not any(c.isupper() for c in line_lower):
            return True
    
    return False


def clean_text(text, page_title=""):
    """Clean extracted text by removing junk lines."""
    lines = text.split("\n")
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if is_junk_line(line):
            continue
        
        cleaned_lines.append(line)
    
    # Remove duplicate consecutive lines
    final_lines = []
    prev_line = ""
    for line in cleaned_lines:
        if line.lower() != prev_line.lower():
            final_lines.append(line)
            prev_line = line
    
    return "\n".join(final_lines)


def clean_all_data(data):
    """Clean all scraped data."""
    cleaned = {}
    for title, text in data.items():
        print(f"Cleaning: {title} ... ", end="", flush=True)
        cleaned[title] = clean_text(text, title)
        print(f"done ({len(cleaned[title])} chars)")
    
    return cleaned


if __name__ == "__main__":
    # Test with a sample
    sample_text = """Skip to content
    Home
    About BVRIT Hyderabad
    BVRIT Hyderabad College of Engineering for Women
    This is important content about the college.
    Copyright 2024
    Privacy Policy
    """
    cleaned = clean_text(sample_text)
    print("Original:", repr(sample_text))
    print("Cleaned:", repr(cleaned))
