# Retrieval-Augmented Generation (RAG) Basics

RAG is a pattern where a system:
1) **retrieves** relevant snippets from a document collection
2) **uses those snippets** to craft a final answer

Even without a large language model, retrieval is useful:
- you can quote your own docs
- you can keep answers grounded and consistent
- you can explain "where the answer came from"

## Why BM25?
BM25 is a classic retrieval algorithm:
- it rewards documents that contain your query terms
- it down-weights overly common terms
- it normalizes by document length so huge docs don’t dominate

## Practical Tip
Keep documents as multiple smaller files and chunk them into sections.
Smaller chunks improve relevance and speed.
