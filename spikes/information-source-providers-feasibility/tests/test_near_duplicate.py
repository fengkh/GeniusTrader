from src.dedup.near_duplicate import jaccard_similarity, near_duplicate_pairs


def test_near_duplicate_similarity():
    assert jaccard_similarity("重大合同 公告", "重大合同 公告") == 1.0
    pairs = near_duplicate_pairs([{"title": "重大合同 公告"}, {"title": "重大合同 公告"}])
    assert pairs
