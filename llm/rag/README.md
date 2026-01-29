# Stockfish → RAG System


This module converts Stockfish analysis into human explanations.


## Pipeline
1. Stockfish JSON → Engine Signal Vector (ESV)
2. ESV → Deterministic RAG retrieval
3. RAG context → Mode-2 LLM explanation


## Hard Guarantees
- No chess calculation outside Stockfish
- No hallucinated moves or tactics
- Deterministic behavior


## DO NOT
- Add semantic search
- Add move suggestions
- Bypass ESV mapping