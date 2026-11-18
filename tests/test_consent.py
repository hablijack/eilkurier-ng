"""Consent walls: accept them like a reader would, then read the article. Pay walls stay pay walls."""

import json

import httpx
from factories import add_article, add_source
from sqlalchemy import select

from eilkurier import collect, consent
from eilkurier.collect import extract_fulltext
from eilkurier.db import Article, Status
from eilkurier.http import HostThrottle

ARTICLE = "https://www.golem.de/news/bruecke-2611-1.html"
WALL = "https://www.golem.de/sonstiges/zustimmung/auswahl.html"
SET_COOKIE = "https://www.golem.de/abo/setconsentcookie.php"


def page(title: str, head: str = "") -> str:
    """An article with its own text (trafilatura's deduplication would drop text other tests already used)."""
    words = " ".join(
        f"{title} Absatz {i} erzählt vom Rechenzentrum in Kemnath und seinen Kosten." for i in range(4)
    )
    body = "".join(f"<p>{words} Teil {n}.</p>" for n in range(4))
    article = f"<article><h1>{title}</h1>{body}</article>"
    return f"<html><head><title>{title}</title>{head}</head><body>{article}</body></html>"


def golem_wall(version: str = "|261101", cookie_url: str = "https://www.golem.de/abo") -> str:
    config = {
        "cookieName": "golem_consent20",
        "cookieVersion": version,
        "cookieExpire": 90,
        "cookieUrl": cookie_url,
    }
    return f"<html><body><script>GolemConsent.setCustomConfig({json.dumps(config)});</script></body></html>"


def golem(web, **wall) -> None:
    """Like golem.de: without the consent cookie every article redirects to the consent page."""

    def article(request: httpx.Request) -> httpx.Response:
        if "golem_consent20=cmp|261101" in request.headers.get("cookie", ""):
            return httpx.Response(200, text=page("Golem"))
        return httpx.Response(302, headers={"location": f"{WALL}?from={ARTICLE}"})

    def set_cookie(request: httpx.Request) -> httpx.Response:
        value = "cmp" + request.url.params["version"]
        return httpx.Response(
            200, headers={"set-cookie": f"golem_consent20={value}; path=/; domain=golem.de"}
        )

    web.add(ARTICLE, article)
    web.add(WALL, golem_wall(**wall))
    web.add(SET_COOKIE, set_cookie)


def test_golem_consent_is_given_once_and_the_article_loads(web) -> None:
    golem(web)
    http = web.client()
    page = consent.get_page(http, ARTICLE)
    assert str(page.url) == ARTICLE and extract_fulltext(page.text, ARTICLE)
    consent.get_page(http, ARTICLE)  # the cookie stays in the client: no second consent
    assert sum(r.url.path == "/abo/setconsentcookie.php" for r in web.requests) == 1


def test_fulltext_step_reads_golem_articles(session, settings, web) -> None:
    golem(web)
    source = add_source(session, name="Golem", url="https://rss.golem.de/rss.php")
    add_article(session, source, "Brücke öffnet", url=ARTICLE, fulltext_status="pending")
    assert collect.fetch_fulltexts(session, web.client(), settings, HostThrottle(0)) == 1
    assert session.scalar(select(Article)).fulltext_status == Status.DONE


def test_consent_is_never_sent_to_another_host(web) -> None:
    golem(web, cookie_url="https://tracker.example.org")
    page = consent.get_page(web.client(), ARTICLE)
    assert "/zustimmung/" in page.url.path  # left as it is: the article stays a teaser
    assert not any(r.url.host == "tracker.example.org" for r in web.requests)


def test_a_changed_consent_version_is_read_from_the_page(web) -> None:
    golem(web, version="|270101")  # site bumped the version; the article checks the old one in this fake
    consent.get_page(web.client(), ARTICLE)
    sent = [r for r in web.requests if r.url.path == "/abo/setconsentcookie.php"]
    assert sent[0].url.params["version"] == "|270101"


def test_paid_articles_stay_teasers() -> None:
    paid = page(
        "KI-Server",
        head='<script type="application/ld+json">{"isAccessibleForFree": false}</script>',
    )
    assert extract_fulltext(paid) is None
    free = page("Frei", head='<script type="application/ld+json">{"isAccessibleForFree":true}</script>')
    assert extract_fulltext(free)
