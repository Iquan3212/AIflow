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
# implementation has to conform to this, not the other way around. 768
# was originally chosen to match a real provider (Gemini, since removed
# in Phase 11 - see embeddings.py's module docstring) via its Matryoshka
# output_dimensionality truncation; kept unchanged since MockEmbeddingProvider
# (the only provider now) already produces vectors of this length and
# changing it would require a schema migration for no actual benefit.
EMBEDDING_DIMENSION = 768

# ---- upload validation ------------------------------------------------

ALLOWED_FILE_TYPES = ("pdf", "docx", "txt")
MAX_UPLOAD_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB - generous for an agency policy/menu document, not a media dump

# ---- chunking -----------------------------------------------------------
# Character-based, not token-based - simple, deterministic, and doesn't
# couple the ingestion pipeline to any one tokenizer. Sized to comfortably
# hold a paragraph or two of real agency content (a menu section, one
# FAQ answer, one policy clause) without being so large that a single
# irrelevant chunk crowds out the context budget in retrieval.py.
CHUNK_SIZE_CHARS = 1000
CHUNK_OVERLAP_CHARS = 150
MIN_CHUNK_CHARS = 40  # a chunk shorter than this is merged into its neighbor rather than indexed on its own

# ---- retrieval ------------------------------------------------------
# See app/services/knowledge/retrieval.py. The relevance cutoff is a
# cosine-similarity threshold (1.0 = identical, 0.0 = unrelated) - chunks
# below it are dropped rather than forced into the prompt, so "nothing
# relevant was found" is a real, honest outcome the LLM can act on (see
# llm_reply.py's grounding instruction) instead of always injecting the
# top-k regardless of quality. See MOCK_RELEVANCE_THRESHOLD below for the
# actual value used (Phase 11: "mock" is the only embedding provider -
# see embeddings.py's module docstring for why Gemini was removed).
DEFAULT_TOP_K = 4
MAX_CONTEXT_CHARS = 4000  # hard cap on how much retrieved text can ever reach one synthesis call

# ---- mock embedding provider (see embeddings.py) -----------------------
# A live UI bug report (Search Knowledge always returning "No relevant
# content found" for real, obviously-answerable questions against real
# uploaded documents) traced all the way down to MockEmbeddingProvider's
# original algorithm: a whole-string SHA256 hash seeding an RNG has ZERO
# relationship to the text's actual words, so cosine similarity between
# any two different strings was statistical noise regardless of true
# relevance (confirmed live: exact-text queries scored 1.0 through the
# real API, proving the pipeline/pgvector/threshold/tenant-filter code was
# all correct - only cross-text similarity was meaningless). Fixed by
# rewriting MockEmbeddingProvider as a deterministic, zero-network,
# zero-token hashed bag-of-words ("feature hashing") embedding: shared
# vocabulary between a query and a chunk now produces genuine, measurable
# cosine similarity, while remaining fully deterministic and going through
# the exact same pgvector cosine-distance/HNSW path as every other
# provider - never a keyword-matching bypass of that architecture.
#
# MOCK_EMBEDDING_STOPWORDS strips common English function words before
# hashing, so a query like "What is the price of X?" is compared on
# {"price", "x"} rather than being diluted by {"what", "is", "the", "of"}
# tokens that appear in nearly every document and add noise rather than
# signal.
MOCK_EMBEDDING_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "of", "in", "on", "at", "to", "for", "with", "by", "from", "as",
    "and", "or", "but", "if", "so", "than", "that", "this", "these", "those",
    "i", "you", "we", "they", "he", "she", "it", "what", "which", "who",
    "do", "does", "did", "have", "has", "had", "can", "could", "will",
    "would", "should", "not", "no", "yes",
})

# Measured empirically (see the migration/fix that added this constant)
# against this exact bag-of-words scheme, using real uploaded agency
# documents and real natural-language questions: genuinely relevant
# matches scored 0.50-0.63, while an unrelated query's best (wrong) match
# scored at most ~0.12 - 0.3 sits with wide margin on both sides of that
# real, measured gap. A sparse hashed bag-of-words vector's cosine-
# similarity scale is not directly comparable to a dense neural
# embedding's, which is why EmbeddingProvider.relevance_threshold
# (embeddings.py) is a per-provider attribute rather than one bare
# module constant - even though "mock" is the only provider today
# (Phase 11 removed Gemini, the other one that ever existed here).
MOCK_RELEVANCE_THRESHOLD = 0.3
