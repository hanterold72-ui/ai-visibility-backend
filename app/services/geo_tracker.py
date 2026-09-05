import re
import httpx
from app.config import settings

GEMINI_MODELS = ["gemini-3.6-flash", "gemini-3.1-flash", "gemini-2.5-flash"]

class CitationResult:
    def __init__(self, is_cited, citation_context=None, source_url=None, raw_answer_snippet="", engine_used=None):
        self.is_cited = is_cited
        self.citation_context = citation_context
        self.source_url = source_url
        self.raw_answer_snippet = raw_answer_snippet
        self.engine_used = engine_used

    def dict(self):
        return {
            "is_cited": self.is_cited,
            "citation_context": self.citation_context,
            "source_url": self.source_url,
            "raw_answer_snippet": self.raw_answer_snippet,
            "engine_used": self.engine_used,
        }

class GeoTrackerService:
    async def check_perplexity(self, query: str, target_domain: str) -> CitationResult:
        try:
            headers = {
                "Authorization": f"Bearer {settings.PERPLEXITY_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "sonar",
                "messages": [{"role": "user", "content": query}],
                "return_citations": True,
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post("https://api.perplexity.ai/chat/completions", json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            answer = data["choices"][0]["message"]["content"]
            citations = data.get("citations", [])
            pattern = re.compile(re.escape(target_domain), re.IGNORECASE)
            is_cited = bool(pattern.search(answer)) or any(pattern.search(u) for u in citations)

            return CitationResult(
                is_cited=is_cited,
                citation_context=answer[:200] if is_cited else None,
                source_url=citations[0] if citations else None,
                raw_answer_snippet=answer[:400],
                engine_used="perplexity",
            )
        except Exception as e:
            return CitationResult(
                is_cited=False,
                raw_answer_snippet=f"Ошибка Perplexity: {str(e)[:150]}",
                engine_used="perplexity",
            )

    async def check_gemini(self, query: str, target_domain: str) -> CitationResult:
        last_error = None
        for model in GEMINI_MODELS:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={settings.GOOGLE_GEMINI_API_KEY}"
                payload = {
                    "contents": [{"parts": [{"text": query}]}],
                    "tools": [{"google_search": {}}],
                }
                async with httpx.AsyncClient(timeout=40.0) as client:
                    resp = await client.post(url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()

                cand = data["candidates"][0]
                parts = cand.get("content", {}).get("parts", [])
                answer = "".join(p.get("text", "") for p in parts)
                chunks = cand.get("groundingMetadata", {}).get("groundingChunks", [])
                urls = [c.get("web", {}).get("uri", "") for c in chunks if c.get("web")]
                pattern = re.compile(re.escape(target_domain), re.IGNORECASE)
                is_cited = bool(pattern.search(answer)) or any(pattern.search(u) for u in urls)

                return CitationResult(
                    is_cited=is_cited,
                    citation_context=answer[:300] if is_cited else None,
                    source_url=urls[0] if urls else None,
                    raw_answer_snippet=answer[:500],
                    engine_used=f"gemini:{model}",
                )
            except Exception as e:
                last_error = f"{model}: {str(e)[:120]}"
                continue

        return CitationResult(
            is_cited=False,
            raw_answer_snippet=f"Все модели Gemini недоступны. Последняя ошибка: {last_error}",
            engine_used="gemini",
        )

    async def check(self, query: str, target_domain: str, engine: str) -> CitationResult:
        if engine == "perplexity":
            return await self.check_perplexity(query, target_domain)
        if engine == "gemini":
            return await self.check_gemini(query, target_domain)
        return CitationResult(
            is_cited=False,
            raw_answer_snippet=f"Неизвестный engine: {engine}",
        )

    def is_configured(self, engine: str) -> bool:
        if engine == "perplexity":
            return bool(settings.PERPLEXITY_API_KEY)
        if engine == "gemini":
            return bool(settings.GOOGLE_GEMINI_API_KEY)
        return False