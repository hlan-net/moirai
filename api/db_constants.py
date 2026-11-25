# Mongo Constants for Mango Queries
MONGO_ELEM_MATCH = "$elemMatch"
MONGO_REGEX = "$regex"
MONGO_OR = "$or"
MONGO_IN = "$in"
MONGO_GT = "$gt"
MONGO_GTE = "$gte"
MONGO_LTE = "$lte"

# Article search (#387). The Mango index holds every field the search reads,
# so a search is answered from the index without loading a document.
# `use_index` names the design document, so the index is created with one.
ARTICLE_SEARCH_INDEX = "idx_search_text"
ARTICLE_SEARCH_TEXT_FIELDS = ("title", "summary", "content")
ARTICLE_SEARCH_INDEX_FIELDS = ["published", *ARTICLE_SEARCH_TEXT_FIELDS]

# A Mango index holds only the documents that have every indexed field, so an
# article without a `summary` or `content` would be invisible to the search.
# Ingestion writes both; this partial index lists the articles that lack one
# (written by older code or by hand), and start-up gives them an empty string.
# It is normally empty, so reading it costs nothing.
ARTICLE_SEARCH_GAPS_INDEX = "idx_search_gaps"
ARTICLE_SEARCH_BACKFILL_FIELDS = ("summary", "content")
ARTICLE_SEARCH_GAPS_SELECTOR = {
    MONGO_OR: [
        clause
        for field in ARTICLE_SEARCH_BACKFILL_FIELDS
        for clause in ({field: {"$exists": False}}, {field: None})
    ]
}
