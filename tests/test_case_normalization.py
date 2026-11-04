from osint_agent.profiling.leads import LeadQueue
from osint_agent.profiling.normalizers import fold_key
from osint_agent.profiling.pivots import search_queries, username_variants


def test_fold_key_case_whitespace_unicode():
    assert fold_key("  JohnDoe  ") == fold_key("johndoe")
    assert fold_key("สมชาย  ใจดี") == fold_key("สมชาย ใจดี")


def test_username_variants_dedupe_casefold():
    variants = username_variants("John.Doe")
    assert len({fold_key(v) for v in variants}) == len(variants)
    assert "John.Doe" in variants


def test_lead_queue_dedupes_case_insensitively():
    queue = LeadQueue()
    assert queue.add("JohnDoe", "username", "first")
    assert not queue.add("johndoe", "username", "second")


def test_name_queries_are_casefold_deduped():
    queries = search_queries("John Doe", "name")
    assert len({fold_key(q) for q in queries}) == len(queries)
