"""
Debug script to check why EAMCET questions aren't being answered.
"""
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))
load_dotenv()

import config
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

embeddings = OpenAIEmbeddings(
    model=config.EMBEDDING_MODEL,
    openai_api_key=os.getenv("OPENROUTER_API_KEY"),
    openai_api_base=config.OPENROUTER_BASE_URL,
)

vs = Chroma(
    collection_name=config.CHROMA_COLLECTION_NAME,
    embedding_function=embeddings,
    persist_directory=str(config.CHROMA_DIR),
)

# 1. Check total chunks
all_data = vs._collection.get()
print(f"Total chunks: {len(all_data['ids'])}")
print()

# 2. Find EAMCET-related sections
eamcet_sections = set()
for i, meta in enumerate(all_data["metadatas"]):
    section = meta.get("section", "")
    doc_text = all_data["documents"][i][:200] if i < len(all_data["documents"]) else ""
    if "eamcet" in section.lower() or "eamcet" in doc_text.lower():
        eamcet_sections.add(section)

print(f"EAMCET-related sections found: {len(eamcet_sections)}")
for s in sorted(eamcet_sections):
    print(f"  - {s}")
print()

# 3. Test retrieval for EAMCET query
query = "What is the expected TS EAMCET cutoff rank for BVRIT Hyderabad?"
results = vs.similarity_search_with_relevance_scores(query, k=5)
print(f"Retrieval for: '{query}'")
print(f"Number of results: {len(results)}")
print()
for i, (doc, score) in enumerate(results):
    section = doc.metadata.get("section", "N/A")
    print(f"  [{i}] Score: {score:.4f} | Section: {section}")
    print(f"      Preview: {doc.page_content[:150]}")
    print()

# 3b. Print full content of EAMCET Ranks section
print("=" * 60)
print("Full content of EAMCET Ranks sections:")
print("=" * 60)
for i, meta in enumerate(all_data["metadatas"]):
    section = meta.get("section", "")
    if "EAMCET Ranks" in section:
        print(f"\n--- Section: {section} ---")
        print(f"Text length: {len(all_data['documents'][i])} chars")
        print(all_data['documents'][i][:500])
print()

# 4. Also test with simpler query
query2 = "EAMCET cutoff ranks"
results2 = vs.similarity_search_with_relevance_scores(query2, k=5)
print(f"Retrieval for: '{query2}'")
print(f"Number of results: {len(results2)}")
print()
for i, (doc, score) in enumerate(results2):
    section = doc.metadata.get("section", "N/A")
    print(f"  [{i}] Score: {score:.4f} | Section: {section}")
    print(f"      Preview: {doc.page_content[:150]}")
    print()