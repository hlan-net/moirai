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
