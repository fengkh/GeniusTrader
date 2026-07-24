from src.dedup.exact import exact_deduplicate


def test_exact_deduplicate_keeps_first_record():
    records = [{"deduplication_key": "a", "title": "first"}, {"deduplication_key": "a", "title": "second"}]
    assert exact_deduplicate(records) == [{"deduplication_key": "a", "title": "first"}]
