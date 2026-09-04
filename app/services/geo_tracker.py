import re
import httpx
from app.config import settings

class CitationResult:
    def __init__(self, is_cited, citation_context=None, source_url=None, raw_answer_snippet=""):
        self.is_cited = is_cited
        self.citation_context = citation_context
        self.source_url = source_url
        self.raw_answer_snippet = raw_answer_snippet
    
    def dict(self):
        return {
            "is_cited": self.is_cited,
            "citation_context": self.citation_context,
            "source_url": self.source_url,
            "raw_answer_snippet": self.raw_answer_snippet
        }

class GeoTrackerService:
    async def check_perplexity(self, query: str, target_domain: str) -> CitationResult:
        headers = {
            "Authorization": f"Bearer {settings.PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "sonar",
            "messages": [{"role": "user", "content": query}],
            "return_citations": True
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.perplexity.ai/chat/completions",
                json=payload, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
        
        answer = data["choices"][0]["message"]["content"]
        citations = data.get("citations", [])
        pattern = re.compile(re.escape(target_domain), re.IGNORECASE)
        
        is_cited = bool(pattern.search(answer)) or any(pattern.search(url) for url in citations)
        
        return CitationResult(
            is_cited=is_cited,
            citation_context=answer[:200] if is_cited else None,
            source_url=citations[0] if citations else None,
            raw_answer_snippet=answer[:400]
        )
    
    async def check(self, query: str, target_domain: str, engine: str) -> CitationResult:
        if engine == "perplexity":
            return await self.check_perplexity(query, target_domain)
        raise NotImplementedError(f"Engine {engine} not implemented")
    
    def is_configured(self, engine: str) -> bool:
        return engine == "perplexity" and bool(settings.PERPLEXITY_API_KEY)
