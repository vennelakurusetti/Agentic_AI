"""
intent_classifier.py - Intent classification for the College FAQ Chatbot.
Routes user input to appropriate handlers before the RAG pipeline.
"""

import re
from typing import Tuple

# Intent categories
INTENT_GREETING = "greeting"
INTENT_SMALL_TALK = "small_talk"
INTENT_ABUSIVE = "abusive"
INTENT_UNRELATED = "unrelated"
INTENT_COLLEGE_QUERY = "college_query"

# Greeting patterns
GREETING_PATTERNS = [
    r"^(hi|hello|hey|heyy|heya|howdy|yo|sup)\b",
    r"^(good\s*(morning|afternoon|evening|day|night))\b",
    r"^(greetings|namaste|vanakkam|namaskar)\b",
    r"^(what'?s\s*up|wassup|how'?s\s*it\s*going)\b",
    r"^(nice\s*to\s*meet\s*you|pleased\s*to\s*meet)\b",
]

# Small talk patterns
SMALL_TALK_PATTERNS = [
    r"^(thanks|thank\s*you|thankyou|thx|ty)\b",
    r"^(bye|goodbye|see\s*you|cya|gotta\s*go|have\s*a\s*great\s*day)\b",
    r"^(who\s*are\s*you|what\s*are\s*you|tell\s*me\s*about\s*yourself)\b",
    r"^(what\s*can\s*you\s*do|how\s*can\s*you\s*help|what\s*are\s*your\s*features)\b",
    r"^(ok|okay|alright|sure|got\s*it|understood|i\s*see)\b",
    r"^(nice|cool|awesome|great|good|perfect|excellent)\s*!*$",
    r"^(how\s*are\s*you|how'?re\s*you|how\s*are\s*things|how'?s\s*it\s*going)\s*\?*$",
    r"^(i'?m\s*(fine|good|great|okay|doing\s*well),?\s*(thanks|thank\s*you)?)\b",
    r"^(no\s*problem|my\s*pleasure|you'?re\s*welcome|anytime)\b",
    r"^(that'?s\s*(helpful|useful|great|good|perfect))\b",
]

# Abusive/offensive patterns
ABUSIVE_PATTERNS = [
    r"\b(fuck|fck|f\*ck|shit|damn|bitch|asshole|bastard|crap|dick)\b",
    r"\b(stupid|idiot|dumb|moron|loser|jerk|suck)\b",
    r"\b(hate\s*you|shut\s*up|go\s*away|leave\s*me\s*alone)\b",
    r"\b(you\s*(are\s*)?(useless|terrible|awful|horrible|worst))\b",
]

# Unrelated query patterns (explicitly not college-related)
UNRELATED_PATTERNS = [
    r"\b(weather|forecast|rain|temperature|climate)\b",
    r"\b(joke|jokes|funny|humor|laugh)\b",
    r"\b(recipe|cooking|food\s*recipe|baking)\b",
    r"\b(movie|film|song|music|album|actor|actress|celebrity)\b",
    r"\b(game|gaming|playstation|xbox|nintendo|video\s*game)\b",
    r"\b(sport|sports|football|cricket|basketball|tennis|soccer)\b",
    r"\b(politics|election|president|prime\s*minister|government)\b",
    r"\b(stock|stock\s*market|trading|investment|crypto|bitcoin)\b",
    r"\b(health|disease|symptom|medicine|doctor|hospital|treatment)\b",
    r"\b(travel|trip|vacation|holiday|tourist|destination|hotel)\b",
    r"\b(news|current\s*affairs|headline|breaking\s*news)\b",
    r"\b(programming|code|python|javascript|java|react|angular)\b",
    r"\b(how\s*to\s*(cook|bake|fix|repair|build|make|create))\b",
]

# College-related keywords (to detect if query is about the college)
COLLEGE_KEYWORDS = [
    # General
    r"\b(bvrit|bvrith|b\.v\.rit|college|institute|university|campus)\b",
    r"\b(hyderabad|telangana)\b",
    # Academics
    r"\b(admission|admissions|apply|application|eligibility|seat|seats)\b",
    r"\b(fee|fees|tuition|scholarship|financial\s*aid|payment)\b",
    r"\b(course|courses|program|programs|branch|branches|stream|streams)\b",
    r"\b(b\.tech|btech|bachelor|m\.tech|mtech|master|ph\.d|phd|diploma)\b",
    r"\b(cse|ece|eee|it|ai|ml|artificial\s*intelligence|machine\s*learning)\b",
    r"\b(computer\s*science|electronics|electrical|information\s*technology)\b",
    r"\b(syllabus|curriculum|subject|subjects|semester|academic\s*calendar)\b",
    r"\b(rank|ranks|eamcet|eapcet|ts\s*eamcet|ts\s*eapcet|cet|counseling|counselling)\b",
    r"\b(cutoff|cut\s*off|closing\s*rank|opening\s*rank)\b",
    # Placements
    r"\b(placement|placements|placed|recruit|recruitment|recruiter|company|companies)\b",
    r"\b(offer|package|salary|intern|internship|training|tpo|placement\s*cell)\b",
    r"\b(job|jobs|career|careers|employ|employment|hiring)\b",
    # Departments & Faculty
    r"\b(department|departments|hod|head\s*of\s*department|faculty|professor|teacher)\b",
    r"\b(lab|laboratory|libraries|library|classroom|workshop)\b",
    # Facilities
    r"\b(hostel|mess|cafeteria|canteen|food|transport|bus|gym|sports|library)\b",
    r"\b(facility|facilities|infrastructure|wifi|internet|smart\s*classroom)\b",
    # Research
    r"\b(research|publication|patent|project|conference|journal|ph\.d)\b",
    # Student Life
    r"\b(club|clubs|society|fest|cultural|technical\s*fest|event|activity)\b",
    r"\b(nss|ieee|csi|acm|rotaract|sports|yoga|music|dance)\b",
    # About
    r"\b(about|vision|mission|history|founder|management|principal|director)\b",
    r"\b(accreditation|naac|nba|nirf|ranking|ranked|autonomous)\b",
    r"\b(alumni|alumnus|alma\s*mater|placement\s*record|achievement)\b",
    r"\b(contact|address|phone|email|website|location|map|reach)\b",
    r"\b(transportation|bus\s*route|pickup|drop|conveyance)\b",
    r"\b(hostel|accommodation|room|dormitory|boarding)\b",
    r"\b(scholarship|financial\s*aid|fee\s*waiver|concession)\b",
    r"\b(document|documents|certificate|certificates|verification)\b",
    r"\b(transfer|migration|tc|conduct|bonafide|study\s*certificate)\b",
]

# Response templates
GREETING_RESPONSES = [
    "Hello! 👋 Welcome to the BVRIT Hyderabad College FAQ Chatbot. I can help you with questions about admissions, departments, placements, campus facilities, and more. How can I assist you today?",
    "Hi there! 😊 I'm the BVRIT Hyderabad FAQ assistant. Feel free to ask me anything about the college — from admissions to placements, departments to campus life!",
    "Hey! Welcome to BVRIT Hyderabad's FAQ chatbot. 🎓 I'm here to answer your questions about the college. What would you like to know?",
]

SMALL_TALK_RESPONSES = {
    "thanks": "You're welcome! 😊 If you have any more questions about BVRIT Hyderabad, feel free to ask.",
    "bye": "Goodbye! 👋 Feel free to come back anytime if you have more questions about BVRIT Hyderabad.",
    "who_are_you": "I'm the BVRIT Hyderabad College FAQ Chatbot! 🎓 I'm here to answer your questions about admissions, departments, placements, campus facilities, research, and more — all based on the official college knowledge base.",
    "what_can_you_do": "I can answer questions about BVRIT Hyderabad College of Engineering for Women! 🎓 Here's what I can help with:\n\n• 📋 Admissions process and requirements\n• 🏫 Departments and programs offered\n• 💼 Placements and internships\n• 🏛️ Campus facilities and infrastructure\n• 🔬 Research and publications\n• 🎉 Student activities and clubs\n• 📞 Contact information\n\nJust ask me anything about the college!",
    "how_are_you": "I'm doing great, thank you! 😊 Ready to help you with any questions about BVRIT Hyderabad. What would you like to know?",
    "default": "Thanks for your message! 😊 Is there anything specific about BVRIT Hyderabad you'd like to know? I can help with admissions, placements, departments, and more.",
}

ABUSIVE_RESPONSE = "I'm here to help with questions about BVRIT Hyderabad. Please keep the conversation respectful. 🙏 How can I assist you with college-related queries?"

UNRELATED_RESPONSE = "I can only answer questions related to BVRIT Hyderabad based on the uploaded knowledge base. 🎓 Please ask me something about the college — admissions, placements, departments, facilities, or anything else!"


def classify_intent(text: str) -> str:
    """Classify the user's input into an intent category."""
    text_lower = text.lower().strip()

    # Check for abusive content first (highest priority)
    for pattern in ABUSIVE_PATTERNS:
        if re.search(pattern, text_lower):
            return INTENT_ABUSIVE

    # Check for greetings
    for pattern in GREETING_PATTERNS:
        if re.match(pattern, text_lower):
            return INTENT_GREETING

    # Check for small talk
    for pattern in SMALL_TALK_PATTERNS:
        if re.match(pattern, text_lower):
            return INTENT_SMALL_TALK

    # Check if it's a college-related query (must check before unrelated)
    for pattern in COLLEGE_KEYWORDS:
        if re.search(pattern, text_lower):
            return INTENT_COLLEGE_QUERY

    # Check for explicitly unrelated topics
    for pattern in UNRELATED_PATTERNS:
        if re.search(pattern, text_lower):
            return INTENT_UNRELATED

    # If the text is very short and doesn't match anything, treat as unrelated
    if len(text_lower.split()) <= 2:
        return INTENT_UNRELATED

    # Default: treat as college query (the RAG pipeline will handle "not available" if not found)
    return INTENT_COLLEGE_QUERY


def get_small_talk_response(text: str) -> str:
    """Get an appropriate small talk response."""
    text_lower = text.lower().strip()

    if re.match(r"^(thanks|thank\s*you|thankyou|thx|ty)\b", text_lower):
        return SMALL_TALK_RESPONSES["thanks"]
    elif re.match(r"^(bye|goodbye|see\s*you|cya|gotta\s*go|have\s*a\s*great\s*day)\b", text_lower):
        return SMALL_TALK_RESPONSES["bye"]
    elif re.match(r"^(who\s*are\s*you|what\s*are\s*you|tell\s*me\s*about\s*yourself)\b", text_lower):
        return SMALL_TALK_RESPONSES["who_are_you"]
    elif re.match(r"^(what\s*can\s*you\s*do|how\s*can\s*you\s*help|what\s*are\s*your\s*features)\b", text_lower):
        return SMALL_TALK_RESPONSES["what_can_you_do"]
    elif re.match(r"^(how\s*are\s*you|how'?re\s*you|how\s*are\s*things|how'?s\s*it\s*going)\s*\?*$", text_lower):
        return SMALL_TALK_RESPONSES["how_are_you"]
    else:
        return SMALL_TALK_RESPONSES["default"]


def get_greeting_response() -> str:
    """Get a random greeting response."""
    import random
    return random.choice(GREETING_RESPONSES)


def handle_intent(text: str) -> Tuple[str, str]:
    """
    Classify intent and return (intent, response).
    If intent is COLLEGE_QUERY, response is empty (let RAG handle it).
    """
    intent = classify_intent(text)

    if intent == INTENT_GREETING:
        return intent, get_greeting_response()
    elif intent == INTENT_SMALL_TALK:
        return intent, get_small_talk_response(text)
    elif intent == INTENT_ABUSIVE:
        return intent, ABUSIVE_RESPONSE
    elif intent == INTENT_UNRELATED:
        return intent, UNRELATED_RESPONSE
    else:
        return intent, ""