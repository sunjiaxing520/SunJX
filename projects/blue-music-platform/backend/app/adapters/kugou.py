import html
import json
import re
import time
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from typing import Any

import httpx


KUGOU_CHART_CODE = "8888"
KUGOU_CHART_NAME = "酷狗TOP500"
KUGOU_PAGE_SIZE = 22
KUGOU_PAGE_URL = (
    "https://www.kugou.com/yy/rank/home/{page}-8888.html?from=rank"
)


class KugouAdapterError(RuntimeError):
    pass


@dataclass(frozen=True)
class RankingItem:
    source_song_id: str
    title: str
    artist: str
    rank: int
    popularity: float | None
    cover_url: str | None
    source_url: str | None
    duration_seconds: int | None
    raw_data: dict[str, Any]


@dataclass(frozen=True)
class RankingFetchResult:
    chart_code: str
    chart_name: str
    source_updated_date: date | None
    items: list[RankingItem]


class _KugouPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.description = ""
        self._inside_script = False
        self._script_chunks: list[str] = []
        self.scripts: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        if tag == "meta" and attributes.get("name") == "description":
            self.description = attributes.get("content") or ""
        if tag == "script":
            self._inside_script = True
            self._script_chunks = []

    def handle_data(self, data: str) -> None:
        if self._inside_script:
            self._script_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._inside_script:
            self.scripts.append("".join(self._script_chunks))
            self._inside_script = False
            self._script_chunks = []


def parse_kugou_rank_page(content: str, rank_offset: int = 0) -> RankingFetchResult:
    parser = _KugouPageParser()
    parser.feed(content)

    raw_items: list[dict[str, Any]] | None = None
    for script in parser.scripts:
        match = re.search(
            r"global\.features\s*=\s*(\[.*?\])\s*;",
            script,
            flags=re.DOTALL,
        )
        if match:
            try:
                decoded = json.loads(match.group(1))
            except json.JSONDecodeError as exc:
                raise KugouAdapterError("酷狗榜单数据格式已变化，JSON 解析失败") from exc
            if isinstance(decoded, list):
                raw_items = decoded
                break

    if raw_items is None:
        raise KugouAdapterError("酷狗榜单页面中没有找到歌曲数据")

    updated_match = re.search(r"更新于[：:]\s*(\d{4}-\d{2}-\d{2})", parser.description)
    source_updated_date = (
        date.fromisoformat(updated_match.group(1)) if updated_match else None
    )

    items: list[RankingItem] = []
    for index, raw_item in enumerate(raw_items, start=1):
        source_song_id = str(raw_item.get("Hash") or "").strip()
        file_name = html.unescape(str(raw_item.get("FileName") or "").strip())
        artist = html.unescape(str(raw_item.get("author_name") or "").strip())
        if not source_song_id or not file_name:
            continue

        title = file_name
        artist_prefix = f"{artist} - "
        if artist and file_name.startswith(artist_prefix):
            title = file_name[len(artist_prefix) :].strip()
        elif " - " in file_name and not artist:
            artist, title = (part.strip() for part in file_name.split(" - ", 1))

        encrypted_id = str(raw_item.get("encrypt_id") or "").strip()
        duration = raw_item.get("timeLen")
        items.append(
            RankingItem(
                source_song_id=source_song_id,
                title=title,
                artist=artist or "未知歌手",
                rank=rank_offset + index,
                popularity=None,
                cover_url=None,
                source_url=(
                    f"https://www.kugou.com/mixsong/{encrypted_id}.html"
                    if encrypted_id
                    else None
                ),
                duration_seconds=(
                    round(float(duration)) if isinstance(duration, (int, float)) else None
                ),
                raw_data={
                    "album_id": raw_item.get("album_id"),
                    "privilege": raw_item.get("privilege"),
                    "encrypt_id": encrypted_id or None,
                },
            )
        )

    if not items:
        raise KugouAdapterError("酷狗榜单页面返回了空歌曲列表")

    return RankingFetchResult(
        chart_code=KUGOU_CHART_CODE,
        chart_name=KUGOU_CHART_NAME,
        source_updated_date=source_updated_date,
        items=items,
    )


class KugouRankingAdapter:
    def __init__(self, timeout_seconds: float, max_retries: int) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(1, max_retries)

    def fetch(self, limit: int) -> RankingFetchResult:
        page_count = (limit + KUGOU_PAGE_SIZE - 1) // KUGOU_PAGE_SIZE
        combined: list[RankingItem] = []
        updated_date: date | None = None

        with httpx.Client(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
        ) as client:
            for page in range(1, page_count + 1):
                content = self._fetch_page(client, page)
                parsed = parse_kugou_rank_page(
                    content,
                    rank_offset=(page - 1) * KUGOU_PAGE_SIZE,
                )
                updated_date = updated_date or parsed.source_updated_date
                combined.extend(parsed.items)

        return RankingFetchResult(
            chart_code=KUGOU_CHART_CODE,
            chart_name=KUGOU_CHART_NAME,
            source_updated_date=updated_date,
            items=combined[:limit],
        )

    def _fetch_page(self, client: httpx.Client, page: int) -> str:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = client.get(KUGOU_PAGE_URL.format(page=page))
                response.raise_for_status()
                if "global.features" not in response.text:
                    raise KugouAdapterError("酷狗响应不是预期的榜单页面")
                return response.text
            except (httpx.HTTPError, KugouAdapterError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(0.4 * attempt)

        raise KugouAdapterError(
            f"酷狗榜单第 {page} 页连续请求 {self.max_retries} 次失败"
        ) from last_error


def sample_ranking(limit: int) -> RankingFetchResult:
    titles = [
        ("沿途的风", "蓝乐样例歌手A"),
        ("雨停以后", "蓝乐样例歌手B"),
        ("慢慢告别", "蓝乐样例歌手C"),
        ("夏夜来信", "蓝乐样例歌手D"),
        ("靠近一点", "蓝乐样例歌手E"),
        ("城市失眠", "蓝乐样例歌手F"),
        ("回忆倒带", "蓝乐样例歌手G"),
        ("自由的光", "蓝乐样例歌手H"),
        ("心动预告", "蓝乐样例歌手I"),
        ("孤独星球", "蓝乐样例歌手J"),
        ("日落之前", "蓝乐样例歌手K"),
        ("再见那天", "蓝乐样例歌手L"),
        ("热烈青春", "蓝乐样例歌手M"),
        ("故乡晚风", "蓝乐样例歌手N"),
        ("清醒梦境", "蓝乐样例歌手O"),
    ]
    items = [
        RankingItem(
            source_song_id=f"sample-{index:03d}",
            title=title,
            artist=artist,
            rank=index,
            popularity=float(1000 - index * 10),
            cover_url=None,
            source_url=None,
            duration_seconds=180 + index,
            raw_data={"sample": True},
        )
        for index, (title, artist) in enumerate(titles, start=1)
    ]
    return RankingFetchResult(
        chart_code=KUGOU_CHART_CODE,
        chart_name=f"{KUGOU_CHART_NAME}（固定样例）",
        source_updated_date=date.today(),
        items=items[:limit],
    )
