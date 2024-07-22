from app.utils.string import _remove_double_spaces


def sanitize_fulltext_string(text: str) -> str:
    """Generate a fulltext SQL string for MATCH AGAINST queries. Remove also special SQL characters (wildcards etc.)"""
    if not text:
        return ""
    forbidden_patterns = ["(", ")", ":", "\\", "/", "<", ">", "$", "*", "%", "_", "&", '"']
    # print("".join(forbidden_patterns))
    for pattern in forbidden_patterns:
        text = text.replace(pattern, " ")
    result = _remove_double_spaces(text)
    return result.lower()


def fulltext_search_param(text: str) -> str:
    """
    Generate a fullltext SQLite "MATCH" search parameter.

    Add a wildcard if a keyword is long enough. otherwise, keep the exact match to avoid DB fullscan.
    """

    result = sanitize_fulltext_string(text)
    if any([len(keyword) >= 3 for keyword in result.split(" ")]):
        result += "*"
    return result
