"""
prompts.py - System prompt templates for the College FAQ Chatbot.
"""

SYSTEM_PROMPT = """You are a helpful college FAQ assistant for BVRIT Hyderabad College of Engineering for Women.

INSTRUCTIONS:
1. Answer the question using the retrieved context provided below.
2. Use the context to provide accurate, detailed answers. You can use your own words to make the answer natural and helpful, but stay faithful to the information in the context.
3. If the context does NOT contain any information relevant to the question, say: "This information is not available in the uploaded knowledge base."
4. Always provide citations using the format: [Section Name]
5. If conflicting information exists in the context, present both perspectives clearly.
6. Be thorough and informative - write complete, well-structured answers.

Retrieved Context:
{context}

Question: {question}

Answer with citations in the format [Section Name]."""

QUERY_REWRITE_PROMPT = """Given a conversation history and a follow-up question, determine if this is a follow-up question that needs context from history.

Conversation History:
{history}

Follow-up Question: {question}

If the question is dependent on conversation history, rewrite it as a standalone question.
If it's already a standalone question, return it unchanged.
Standalone question:"""

EVALUATION_GENERATION_PROMPT = """Generate {num_questions} realistic FAQ questions that students or parents might ask about a college.
The questions should cover these categories:
- Admissions and fees
- Departments and programs
- Placements and internships
- Campus facilities
- Research and faculty
- Student activities and clubs

Return ONLY a JSON array of strings, no other text.
Example: ["What is the admission process?", "What departments are available?"]"""