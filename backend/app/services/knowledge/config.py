"""
Centralized, single-source-of-truth constants for the Knowledge Base / RAG
pipeline - imported everywhere a chunking/embedding/upload limit is
needed (app/models.py's Vector column definition, ingestion, retrieval,
the router's upload validation) instead of each module hardcoding its own
copy, which is exactly how earlier phases' keyword lists/fallback strings
drifted out of sync with each other (see manager_agent.py/planner.py's
GMAIL_KEYWORDS history).
"""

# Every embedding written to KnowledgeChunk.embedding MUST be exactly this
# many dimensions - the pgvector column is created with a fixed size (see
# the add_knowledge_base migration), so every EmbeddingProvider
# implementation (mock or real) has to conform to this, not the other way
# around. 768 matches Gemini's text-embedding-004 model, the real
# provider this app is configured to use when EMBEDDING_PROVIDER=gemini
# (see embeddings.py) - MockEmbeddingProvider deliberately produces
# vectors of the same length so both are interchangeable without a schema
# change.
EMBEDDING_DIMENSION = 768

# ---- upload validation ------------------------------------------------

ALLOWED_FILE_TYPES = ("pdf", "docx", "txt")
MAX_UPLOAD_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB - generous for a business policy/menu document, not a media dump

# ---- chunking -----------------------------------------------------------
# Character-based, not token-based - simple, deterministic, and doesn't
# couple the ingestion pipeline to any one tokenizer. Sized to comfortably
# hold a paragraph or two of real business content (a menu section, one
# FAQ answer, one policy clause) without being so large that a single
# irrelevant chunk crowds out the context budget in retrieval.py.
CHUNK_SIZE_CHARS = 1000
CHUNK_OVERLAP_CHARS = 150
MIN_CHUNK_CHARS = 40  # a chunk shorter than this is merged into its neighbor rather than indexed on its own

# ---- retrieval ------------------------------------------------------
# See app/services/knowledge/retrieval.py. RELEVANCE_THRESHOLD is a
# cosine-similarity cutoff (1.0 = identical, 0.0 = unrelated) - chunks
# below it are dropped rather than forced into the prompt, so "nothing
# relevant was found" is a real, honest outcome the LLM can act on (see
# llm_reply.py's grounding instruction) instead of always injecting the
# top-k regardless of quality.
DEFAULT_TOP_K = 4
RELEVANCE_THRESHOLD = 0.55
MAX_CONTEXT_CHARS = 4000  # hard cap on how much retrieved text can ever reach one synthesis call
