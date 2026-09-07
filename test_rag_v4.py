from agent.local_research import LocalFinancialGraphRAG


def test_relevant_excerpt_is_compact_and_query_focused():
    text = ('Background sentence. ' * 30) + 'Revenue growth increased to 12 percent in FY2026. ' + ('Other sentence. ' * 30)
    excerpt = LocalFinancialGraphRAG._relevant_excerpt(text, 'revenue growth FY2026', 500)
    assert len(excerpt) <= 500
    assert 'Revenue growth' in excerpt


def test_rank_docs_prefers_lexical_relevance():
    docs = ['revenue growth margin increased', 'unrelated operations discussion']
    metas = [{}, {}]
    distances = [0.4, 0.4]
    ranked = LocalFinancialGraphRAG._rank_docs('revenue growth', docs, metas, distances)
    assert ranked[0][1] == 0


def test_duplicate_detector():
    assert LocalFinancialGraphRAG._is_near_duplicate(
        'Revenue growth increased and margin improved substantially this year',
        [{ 'revenue', 'growth', 'increased', 'margin', 'improved', 'substantially', 'this', 'year' }]
    )
