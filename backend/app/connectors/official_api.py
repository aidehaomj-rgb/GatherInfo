"""
Official API connector — WTO ePing, EUR-Lex, China Customs, UN Comtrade.
"""
import logging
import os
import asyncio
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urljoin

import httpx

from app.connectors.base import (
    BaseCollector, CollectResult, FetchItem,
    JobStatus, SourceConfig, register_collector,
)
from app.connectors._helpers import result

logger = logging.getLogger(__name__)


@register_collector("official")
class OfficialAPICollector(BaseCollector):
    channel = "official"

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        ac = self.config.auth_config or {}
        atype = ac.get("type", "generic")

        handlers = {
            "wto_eping": self._fetch_wto_eping,
            "eurlex": self._fetch_eurlex,
            "cn_customs": self._fetch_cn_customs,
            "cn_mofcom": self._fetch_cn_mofcom,
            "un_comtrade": self._fetch_un_comtrade,
            "usaspending_dod": self._fetch_usaspending_dod,
            "sam_opportunities": self._fetch_sam_opportunities,
            "generic": self._fetch_generic,
        }
        res = await handlers.get(atype, self._fetch_generic)(keywords, max_items)
        logger.info("OfficialAPI(%s): %d items, %d errors for source %s",
                     atype, len(res.items), len(res.error_log or []), self.config.id)
        return res

    # ── WTO ePing ────────────────────────────────────────────────────────

    async def _fetch_wto_eping(self, keywords: list[str], max_items: int) -> CollectResult:
        items: list[FetchItem] = []
        errors: list[str] = []

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            try:
                resp = await client.get(
                    "https://eping.wto.org/api/v1/notifications",
                    params={"size": min(max_items, 50), "sort": "notificationDate,desc",
                            "keyword": " ".join(keywords) if keywords else None},
                )
                resp.raise_for_status()
                data = resp.json()
                for n in data.get("content", data.get("notifications", [])):
                    items.append(FetchItem(
                        title=n.get("title", "") or n.get("description", "")[:200],
                        content=n.get("description", ""),
                        url=f"https://eping.wto.org/en/Notification/{n.get('id', '')}",
                        published_at=n.get("notificationDate"),
                        language="en", category="tbt_sps",
                        suggested_tags=["channel:wto_eping"],
                        quality_score=0.9,
                        raw_metadata={"api": "wto_eping", "id": n.get("id")},
                    ))
            except Exception as exc:
                errors.append(str(exc))
                logger.error("WTO ePing fetch error for source %s: %s", self.config.id, exc)

        return result(self._new_run_id(), self.config.id, items, errors)

    # ── United States defence procurement ──────────────────────────────

    async def _fetch_usaspending_dod(
        self, keywords: list[str], max_items: int,
    ) -> CollectResult:
        """Collect awarded DoD contracts from the public USAspending API."""
        items: list[FetchItem] = []
        errors: list[str] = []
        seen: set[str] = set()
        end = self.window_end or datetime.now(timezone.utc)
        start = self.window_start or (end - timedelta(days=90))
        search_terms = [str(value).strip() for value in keywords if str(value).strip()]
        if not search_terms:
            search_terms = ["rare earth", "critical mineral", "battery", "defense supply chain"]

        fields = [
            "Award ID", "Recipient Name", "Start Date", "End Date",
            "Award Amount", "Awarding Agency", "Awarding Sub Agency", "Description",
        ]
        auth_config = self.config.auth_config or {}
        minimum_award_amount = float(auth_config.get("minimum_award_amount", 100000))
        concurrency = max(1, min(6, int(auth_config.get("concurrency", 4))))
        per_query = max(3, min(25, max_items // max(1, len(search_terms)) + 2))
        url = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
        async with httpx.AsyncClient(
            timeout=max(30, self.config.timeout_seconds),
            headers={"User-Agent": "GatherInfo/0.9 public procurement monitor"},
        ) as client:
            semaphore = asyncio.Semaphore(concurrency)

            async def fetch_keyword(keyword: str) -> tuple[str, list[dict], str | None]:
                payload = {
                    "filters": {
                        "time_period": [{
                            "start_date": start.date().isoformat(),
                            "end_date": end.date().isoformat(),
                        }],
                        "agencies": [{
                            "type": "awarding", "tier": "toptier",
                            "name": "Department of Defense",
                        }],
                        "award_type_codes": ["A", "B", "C", "D"],
                        "keywords": [keyword],
                    },
                    "fields": fields, "page": 1, "limit": per_query,
                    "sort": "Start Date", "order": "desc",
                }
                try:
                    async with semaphore:
                        response = await client.post(url, json=payload)
                        response.raise_for_status()
                    return keyword, response.json().get("results", []), None
                except Exception as exc:
                    return keyword, [], str(exc)[:180]

            responses = await asyncio.gather(*[
                fetch_keyword(keyword) for keyword in search_terms[:16]
            ])
            for keyword, records, fetch_error in responses:
                if fetch_error:
                    errors.append(f"USAspending[{keyword}]: {fetch_error}")
                    continue
                try:
                    for record in records:
                        award_id = str(record.get("Award ID") or "").strip()
                        recipient = str(record.get("Recipient Name") or "").strip()
                        description = str(record.get("Description") or "").strip()
                        identity = award_id or f"{recipient}|{description}"
                        if not identity or identity in seen:
                            continue
                        amount = record.get("Award Amount")
                        try:
                            numeric_amount = float(amount) if amount is not None else 0
                        except (TypeError, ValueError):
                            numeric_amount = 0
                        if numeric_amount < minimum_award_amount:
                            continue
                        seen.add(identity)
                        amount_text = (
                            f"USD {numeric_amount:,.2f}" if amount is not None else "未披露"
                        )
                        sub_agency = str(record.get("Awarding Sub Agency") or "")
                        title = f"{recipient}获美国国防部合同：{description[:150]}"
                        generated_id = str(record.get("generated_internal_id") or "")
                        detail_url = (
                            f"https://www.usaspending.gov/award/{quote(generated_id, safe='')}/"
                            if generated_id else "https://www.usaspending.gov/search"
                        )
                        content = (
                            f"合同号：{award_id}\n承包企业：{recipient}\n"
                            f"采购机构：{sub_agency or 'Department of Defense'}\n"
                            f"合同内容：{description}\n合同金额：{amount_text}\n"
                            f"开始日期：{record.get('Start Date') or '未披露'}\n"
                            f"结束日期：{record.get('End Date') or '未披露'}"
                        )
                        items.append(FetchItem(
                            title=title, content=content, summary=description[:500],
                            url=detail_url, published_at=record.get("Start Date"),
                            language="zh", category="defense_procurement",
                            suggested_tags=[
                                "country:us", "category:defense_procurement",
                                f"contract:{award_id}" if award_id else "contract:unknown",
                            ],
                            entities={
                                "recipient": recipient, "agency": sub_agency,
                                "contract_id": award_id,
                            },
                            quality_score=0.96, relevance_score=0.9,
                            raw_metadata={
                                "api": "usaspending", "award_id": award_id,
                                "recipient_name": recipient, "description": description,
                                "award_amount": numeric_amount,
                                "minimum_award_amount": minimum_award_amount,
                                "awarding_sub_agency": sub_agency,
                                "contract_start_date": record.get("Start Date"),
                                "contract_end_date": record.get("End Date"),
                                "generated_internal_id": generated_id,
                                "query_keyword": keyword,
                                "date_semantics": "contract_start_date",
                            },
                        ))
                        if len(items) >= max_items:
                            break
                except Exception as exc:
                    errors.append(f"USAspending parse[{keyword}]: {str(exc)[:180]}")
                if len(items) >= max_items:
                    break
        return result(self._new_run_id(), self.config.id, items, errors)

    async def _fetch_sam_opportunities(
        self, keywords: list[str], max_items: int,
    ) -> CollectResult:
        """Collect active DoD opportunities from SAM.gov using a public API key."""
        api_key = str(self.config.api_key or os.getenv(
            self.config.api_key_ref or "SAM_GOV_API_KEY", ""
        )).strip()
        if not api_key:
            return result(
                self._new_run_id(), self.config.id, [],
                ["SAM.gov Public API Key 未配置，请在信息源中填写 API Key。"],
            )

        items: list[FetchItem] = []
        errors: list[str] = []
        seen: set[str] = set()
        end = self.window_end or datetime.now(timezone.utc)
        start = self.window_start or (end - timedelta(days=30))
        endpoint = "https://api.sam.gov/opportunities/v2/search"
        terms = [str(value).strip() for value in keywords if str(value).strip()]
        terms = terms or ["critical minerals", "rare earth", "battery", "defense supply chain"]
        auth_config = self.config.auth_config or {}
        max_queries = max(1, min(8, int(auth_config.get("max_queries_per_run", 6))))
        max_window_days = max(1, min(365, int(auth_config.get("max_window_days", 30))))
        start = max(start, end - timedelta(days=max_window_days))

        async with httpx.AsyncClient(
            timeout=max(30, self.config.timeout_seconds),
            headers={"User-Agent": "GatherInfo/0.9 public procurement monitor"},
        ) as client:
            for keyword in terms[:max_queries]:
                params = {
                    "api_key": api_key, "limit": min(100, max_items),
                    "offset": 0, "postedFrom": start.strftime("%m/%d/%Y"),
                    "postedTo": end.strftime("%m/%d/%Y"),
                    "deptname": "DEPT OF DEFENSE", "q": keyword,
                }
                try:
                    response = await client.get(endpoint, params=params)
                    if response.status_code != 200:
                        try:
                            message = str(response.json().get("message") or "")
                        except Exception:
                            message = ""
                        errors.append(
                            f"SAM.gov[{keyword}]: HTTP {response.status_code}"
                            + (f" - {message[:120]}" if message else "")
                        )
                        if response.status_code == 429:
                            break
                        continue
                    records = response.json().get("opportunitiesData", [])
                except Exception as exc:
                    # Never store the exception URL because it contains api_key.
                    errors.append(f"SAM.gov[{keyword}]: {type(exc).__name__}")
                    continue
                try:
                    for record in records:
                        notice_id = str(record.get("noticeId") or "").strip()
                        if not notice_id or notice_id in seen:
                            continue
                        seen.add(notice_id)
                        title = str(record.get("title") or "").strip()
                        solicitation = str(record.get("solicitationNumber") or "").strip()
                        office = str(record.get("office") or record.get("subTier") or "")
                        description = str(
                            record.get("description") or record.get("additionalInfoLink") or ""
                        )
                        item_url = (
                            f"https://sam.gov/opp/{notice_id}/view"
                            if notice_id else "https://sam.gov/content/opportunities"
                        )
                        items.append(FetchItem(
                            title=title or f"SAM.gov采购机会 {solicitation}",
                            content=(
                                f"公告编号：{solicitation}\n采购机构：{office}\n"
                                f"公告类型：{record.get('type') or '未披露'}\n"
                                f"发布时间：{record.get('postedDate') or '未披露'}\n"
                                f"截止时间：{record.get('responseDeadLine') or '未披露'}\n"
                                f"内容：{description}"
                            ),
                            summary=description[:500], url=item_url,
                            published_at=record.get("postedDate"),
                            language="en", category="defense_procurement",
                            suggested_tags=["country:us", "category:defense_opportunity"],
                            entities={
                                "agency": office, "solicitation_number": solicitation,
                            },
                            quality_score=0.97, relevance_score=0.9,
                            raw_metadata={
                                "api": "sam_opportunities", "notice_id": notice_id,
                                "solicitation_number": solicitation,
                                "notice_type": record.get("type"),
                                "response_deadline": record.get("responseDeadLine"),
                                "query_keyword": keyword,
                                "date_semantics": "notice_posted_date",
                            },
                        ))
                        if len(items) >= max_items:
                            break
                except Exception as exc:
                    errors.append(f"SAM.gov parse[{keyword}]: {str(exc)[:180]}")
                if len(items) >= max_items:
                    break
                await asyncio.sleep(max(0.5, 1 / max(self.config.rate_limit_rps, 0.2)))
        return result(self._new_run_id(), self.config.id, items, errors)

    # ── EUR-Lex ──────────────────────────────────────────────────────────

    async def _fetch_eurlex(self, keywords: list[str], max_items: int) -> CollectResult:
        items: list[FetchItem] = []
        errors: list[str] = []

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            try:
                resp = await client.get(
                    "https://eur-lex.europa.eu/search.html",
                    params={
                        "type": "advanced", "DTS_SUBDOM": "LEGISLATION",
                        "q": " ".join(keywords), "pageSize": min(max_items, 20),
                        "lang": "en",
                    },
                    headers={"Accept": "application/json"},
                )
                if resp.status_code == 200 and "application/json" in resp.headers.get(
                        "Content-Type", ""):
                    for doc in resp.json().get("documents", resp.json().get("results", [])):
                        if isinstance(doc, dict):
                            items.append(FetchItem(
                                title=doc.get("title", ""),
                                url=f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri={doc.get('uri', '')}",
                                content=doc.get("description", ""),
                                published_at=doc.get("date"),
                                language="en", category="regulation",
                                suggested_tags=["channel:eurlex"],
                                quality_score=0.85,
                            ))
            except Exception as exc:
                errors.append(str(exc))
                logger.error("EUR-Lex fetch error for source %s: %s", self.config.id, exc)

        return result(self._new_run_id(), self.config.id, items, errors)

    # ── China Customs ────────────────────────────────────────────────────

    async def _fetch_cn_customs(self, keywords: list[str], max_items: int) -> CollectResult:
        items: list[FetchItem] = []
        errors: list[str] = []

        urls = [
            "http://www.customs.gov.cn/customs/302249/302266/index.html",
            "http://www.customs.gov.cn/customs/302249/zfxxgk/zfxxgkml/index.html",
        ]

        async with httpx.AsyncClient(
            timeout=self.config.timeout_seconds,
            headers={"User-Agent": "GatherInfo/0.4"},
            follow_redirects=True,
        ) as client:
            for url in urls:
                if len(items) >= max_items:
                    break
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "lxml")
                    for link in soup.select("a[href]")[:max_items]:
                        text = link.get_text(strip=True)
                        href = link.get("href", "")
                        if len(text) < 8:
                            continue
                        items.append(FetchItem(
                            title=text, url=urljoin(url, href) if href else "",
                            content=text, language="zh", category="policy",
                            suggested_tags=["source:cn_customs", "country:cn"],
                            quality_score=0.8,
                            raw_metadata={"source": "cn_customs"},
                        ))
                except Exception as exc:
                    errors.append(f"cn_customs: {str(exc)[:80]}")
                    logger.error("China Customs fetch error for source %s: %s",
                                 self.config.id, exc)
                await asyncio.sleep(0.5)

        return result(self._new_run_id(), self.config.id, items, errors)

    # ── MOFCOM ───────────────────────────────────────────────────────────

    async def _fetch_cn_mofcom(self, keywords: list[str], max_items: int) -> CollectResult:
        items: list[FetchItem] = []
        errors: list[str] = []

        urls = [
            "http://www.mofcom.gov.cn/article/b/",
            "http://www.mofcom.gov.cn/article/ae/",
        ]

        async with httpx.AsyncClient(
            timeout=self.config.timeout_seconds,
            headers={"User-Agent": "GatherInfo/0.4"},
            follow_redirects=True,
        ) as client:
            for url in urls:
                if len(items) >= max_items:
                    break
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "lxml")
                    for link in soup.select("a[href]")[:max_items]:
                        text = link.get_text(strip=True)
                        href = link.get("href", "")
                        if len(text) < 8:
                            continue
                        items.append(FetchItem(
                            title=text, url=urljoin(url, href) if href else "",
                            content=text, language="zh", category="policy",
                            suggested_tags=["source:cn_mofcom", "country:cn"],
                            quality_score=0.8,
                            raw_metadata={"source": "cn_mofcom"},
                        ))
                except Exception as exc:
                    errors.append(f"cn_mofcom: {str(exc)[:80]}")
                    logger.error("MOFCOM fetch error for source %s: %s", self.config.id, exc)
                await asyncio.sleep(0.5)

        return result(self._new_run_id(), self.config.id, items, errors)

    # ── UN Comtrade ──────────────────────────────────────────────────────

    async def _fetch_un_comtrade(self, keywords: list[str], max_items: int) -> CollectResult:
        apikey = os.getenv("COMTRADE_API_KEY", "")
        if not apikey:
            logger.warning("COMTRADE_API_KEY not set for source %s", self.config.id)
            return result(self._new_run_id(), self.config.id, [],
                          ["COMTRADE_API_KEY not set"])

        items: list[FetchItem] = []
        errors: list[str] = []

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            try:
                resp = await client.get(
                    "https://comtradeapi.un.org/data/v1/get/C/A/HS",
                    params={"subscription-key": apikey, "reporterCode": "all",
                            "period": "2025,2026", "maxRecords": min(max_items, 50)},
                )
                resp.raise_for_status()
                for rec in resp.json().get("data", [])[:max_items]:
                    items.append(FetchItem(
                        title=f"HS {rec.get('cmdCode', '')} - {rec.get('cmdDesc', '')}",
                        content=str(rec), language="en", category="trade_data",
                        suggested_tags=[f"hs:{rec.get('cmdCode', '')}"],
                        quality_score=0.75,
                        raw_metadata={"api": "un_comtrade", "record": rec},
                    ))
            except Exception as exc:
                errors.append(str(exc))
                logger.error("UN Comtrade fetch error for source %s: %s",
                             self.config.id, exc)

        return result(self._new_run_id(), self.config.id, items, errors)

    # ── Generic REST ─────────────────────────────────────────────────────

    async def _fetch_generic(self, keywords: list[str], max_items: int) -> CollectResult:
        if not self.config.api_endpoint:
            return result(self._new_run_id(), self.config.id, [],
                          ["api_endpoint not configured"])

        items: list[FetchItem] = []
        errors: list[str] = []

        headers = {"Accept": "application/json"}
        api_key = os.getenv(self.config.api_key_ref or "", "")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            try:
                resp = await client.get(
                    self.config.api_endpoint,
                    params={"q": " ".join(keywords)} if keywords else {},
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                results = data if isinstance(data, list) else data.get(
                    "results", data.get("data", []))
                for r in results[:max_items]:
                    if isinstance(r, dict):
                        items.append(FetchItem(
                            title=r.get("title", r.get("name", str(r)[:100])),
                            content=str(r), url=r.get("url", r.get("link", "")),
                            published_at=r.get("date", r.get("published", "")),
                            raw_metadata={"api": "generic", "record": r},
                        ))
            except Exception as exc:
                errors.append(str(exc))
                logger.error("Official generic fetch error for source %s: %s",
                             self.config.id, exc)

        return result(self._new_run_id(), self.config.id, items, errors)
