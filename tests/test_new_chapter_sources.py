"""New chapter sources: dispatch, path checks and the static page lists (no network)."""
import pytest

from komyst.download.sources import chapter_source as cs


@pytest.mark.parametrize("url,name", [
    ("https://comic.naver.com/webtoon/detail?titleId=822657&no=1", "naver_webtoon"),
    ("https://mangadex.org/chapter/dd642d48-eb96-4242-8bd5-49dc24ca9d00", "mangadex"),
    ("https://tapas.io/episode/2135770", "tapas"),
    ("https://comics.inkr.com/title/1-sokora-refugees/chapter/522-vol-1-chapter-1", "inkr"),
    ("https://www.webtoons.com/es/thriller/x/ep-1/viewer?title_no=6967&episode_no=1", "webtoons"),
])
def test_each_source_url_reaches_its_adapter(url, name):
    adapter = cs.select_adapter(url)
    assert adapter.name == name
    adapter.validate_path(url)


@pytest.mark.parametrize("adapter,url", [
    (cs.MANGADEX, "https://mangadex.org/title/abc"),
    (cs.TAPAS, "https://tapas.io/series/abc"),
    (cs.INKR, "https://comics.inkr.com/title/1-x"),
])
def test_non_chapter_pages_are_refused(adapter, url):
    with pytest.raises(cs.SourceError):
        adapter.validate_path(url)


def test_lookalike_hosts_do_not_match_new_sources():
    for url in ("https://mangadex.org.evil.com/chapter/dd642d48-eb96-4242-8bd5-49dc24ca9d00",
                "https://faketapas.io/episode/1"):
        assert cs.select_adapter(url).name == "universal"


def test_tapas_page_list_comes_from_the_lazy_images_in_order():
    html = ('<img class="content__img js-lazy" src="data:," data-src="https://us-a.tapas.io/pc/a.jpg?x=1&amp;y=2">'
            '<img class="avatar" src="https://us-a.tapas.io/u.png">'
            '<img class="content__img js-lazy" data-src="https://us-a.tapas.io/pc/b.jpg">')
    candidates = cs.TAPAS.collect_dom_candidates_from_html(html, "https://tapas.io/episode/1")
    assert [c["url"] for c in candidates] == ["https://us-a.tapas.io/pc/a.jpg?x=1&y=2",
                                              "https://us-a.tapas.io/pc/b.jpg"]
    assert cs.TAPAS.score_cluster(candidates) == 0.97
    assert cs.TAPAS.score_cluster([{"source": "other"}]) is None
