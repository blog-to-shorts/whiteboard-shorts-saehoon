"""STEP 01. 블로그 본문 추출 (Requests + BeautifulSoup).

네이버 블로그는 본문이 iframe(PostView) 안에 있어서 PostView 주소로 바꿔 직접 가져온다.
그 밖의 사이트는 article/main/본문 후보 중 글자가 가장 많은 블록을 쓴다.
추출에 실패하면 원문 직접 입력(--text-file)으로 대체한다(리스크 대응).
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from ..schema import Source, save_json

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
NOISE = re.compile(r"^(공감|댓글|구독|이웃추가|저작자 명시|태그|#\S+$|출처|ⓒ|copyright)", re.I)


def _naver_ids(url: str) -> tuple[str, str] | None:
    u = urlparse(url)
    if "blog.naver.com" not in u.netloc:
        return None
    q = parse_qs(u.query)
    if q.get("blogId") and q.get("logNo"):
        return q["blogId"][0], q["logNo"][0]
    parts = [p for p in u.path.split("/") if p]
    if len(parts) >= 2 and parts[1].isdigit():
        return parts[0], parts[1]
    return None


def _get(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"}, timeout=20)
    r.raise_for_status()
    r.encoding = r.apparent_encoding if r.encoding in (None, "ISO-8859-1") else r.encoding
    return r.text


def _clean_lines(lines: list[str]) -> str:
    out, prev = [], None
    for ln in lines:
        ln = re.sub(r"[​‌‍﻿ ]", " ", ln)
        ln = re.sub(r"\s+", " ", ln).strip()
        if not ln or ln == prev or NOISE.search(ln):
            continue
        out.append(ln)
        prev = ln
    return "\n".join(out)


def _extract_naver(blog_id: str, log_no: str) -> Source:
    url = f"https://blog.naver.com/PostView.naver?blogId={blog_id}&logNo={log_no}&redirect=Dlog&widgetTypeCall=true"
    soup = BeautifulSoup(_get(url), "lxml")
    title_el = soup.select_one(".se-title-text, .pcol1, .se_title .se_textarea, h3.se_textarea")
    title = title_el.get_text(" ", strip=True) if title_el else ""
    body = soup.select_one(".se-main-container, #postViewArea, .se_component_wrap")
    if not body:
        raise ValueError("네이버 본문 영역을 찾지 못했습니다(비공개 글이거나 형식이 다름)")
    paras = body.select(".se-text-paragraph, .se-module-text p, p") or [body]
    text = _clean_lines([p.get_text(" ", strip=True) for p in paras])
    images = []
    for img in body.select("img"):
        src = img.get("data-lazy-src") or img.get("src") or ""
        if "pstatic.net" in src and "sticker" not in src and "map" not in src:
            images.append(re.sub(r"\?type=\w+", "?type=w966", src))
    return Source(url=f"https://blog.naver.com/{blog_id}/{log_no}", title=title, text=text,
                  images=images, site="naver_blog", extractor="requests+bs4:naver_postview")


def _extract_generic(url: str) -> Source:
    soup = BeautifulSoup(_get(url), "lxml")
    for t in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form"]):
        t.decompose()
    og = soup.select_one('meta[property="og:title"]')
    title = (og.get("content") if og else "") or (soup.title.get_text(strip=True) if soup.title else "")
    cands = soup.select("article, main, .entry-content, .post-content, .tt_article_useless_p_margin, #content, .content")
    block = max(cands or [soup.body or soup], key=lambda el: len(el.get_text(" ", strip=True)))
    paras = block.select("p, li, h2, h3") or [block]
    text = _clean_lines([p.get_text(" ", strip=True) for p in paras])
    images = [urljoin(url, i.get("src")) for i in block.select("img[src]")][:20]
    host = urlparse(url).netloc
    return Source(url=url, title=title, text=text, images=images, site=host, extractor="requests+bs4:generic")


def extract(url: str) -> Source:
    ids = _naver_ids(url)
    src = _extract_naver(*ids) if ids else _extract_generic(url)
    if len(src.text) < 200:
        raise ValueError(f"본문이 너무 짧습니다({len(src.text)}자). 원문 직접 입력(--text-file)을 사용하세요.")
    return src


def run(job, *, url: str | None = None, text: str | None = None, title: str | None = None) -> None:
    if text:
        src = Source(url=url or "", title=title or text.strip().splitlines()[0][:60], text=_clean_lines(text.splitlines()),
                     site="manual", extractor="manual_text")
    elif url:
        src = extract(url)
    elif (job.dir / "source.json").is_file():
        job.log.info("STEP01: 기존 source.json 사용")
        return
    else:
        raise ValueError("url 또는 text 가 필요합니다")
    save_json(job.dir / "source.json", src)
    job.log.info("STEP01: '%s' 본문 %d자, 이미지 %d장 (%s)", src.title[:40], len(src.text), len(src.images), src.extractor)
