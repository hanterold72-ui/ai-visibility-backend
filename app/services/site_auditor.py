import time
import socket
import ssl
import httpx
from datetime import datetime
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}

class SiteAuditor:
    async def full_audit(self, domain: str) -> dict:
        domain = (domain or "").strip().lower()
        for pref in ("https://", "http://", "www."):
            if domain.startswith(pref):
                domain = domain[len(pref):]
        domain = domain.split("/")[0]

        issues = []
        cat = {"technical": 100, "security": 100, "seo": 100, "performance": 100}
        meta = {}

        def add(cat_key, points, severity, title, description, recommendation):
            cat[cat_key] = max(0, cat[cat_key] - points)
            issues.append({
                "category": cat_key,
                "severity": severity,
                "title": title,
                "description": description,
                "recommendation": recommendation,
            })

        # 1. DNS
        try:
            import dns.resolver
            ips = [r.address for r in dns.resolver.resolve(domain, "A")]
            meta["ip"] = ips[0]
        except Exception:
            add("technical", 40, "critical", "DNS не найден", "Домен не имеет A-записи", "Проверьте настройки DNS у регистратора")

        # 2. WHOIS возраст домена
        try:
            import whois
            w = whois.whois(domain)
            created = w.creation_date
            if isinstance(created, list):
                created = created[0] if created else None
            if created:
                age = (datetime.utcnow() - created).days
                meta["domain_age_days"] = age
                if age < 365:
                    add("technical", 10, "info", "Молодой домен", f"Домену меньше года ({age} дн.)", "AI-системы больше доверяют старым доменам — наращивайте историю")
        except Exception:
            pass

        # 3. SSL
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((domain, 443), timeout=10) as sock:
                with ctx.wrap_socket(sock, server_hostname=domain) as s:
                    cert = s.getpeercert()
                    end = ssl.cert_time_to_seconds(cert["notAfter"])
                    days_left = int((end - time.time()) / 86400)
                    meta["ssl_days_left"] = days_left
                    if days_left < 14:
                        add("security", 20, "warning", "SSL скоро истечёт", f"Осталось дней: {days_left}", "Продлите SSL-сертификат")
        except Exception:
            add("security", 50, "critical", "Нет SSL-сертификата", "Сайт недоступен по HTTPS", "Установите бесплатный сертификат Let's Encrypt")

        # 4. Загрузка страницы, скорость, заголовки безопасности
        try:
            t0 = time.time()
            async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=HEADERS) as client:
                resp = await client.get(f"https://{domain}")
                ttfb = round(time.time() - t0, 2)
                html = resp.text
                meta["ttfb_sec"] = ttfb
                meta["http_status"] = resp.status_code
                meta["page_size_kb"] = round(len(html) / 1024, 1)

            if resp.status_code >= 400:
                add("technical", 30, "critical", f"HTTP {resp.status_code}", "Главная страница отдаёт ошибку", "Исправьте ошибку сервера")
            if ttfb > 2:
                add("performance", 30, "warning", "Медленный ответ сервера", f"TTFB {ttfb} сек (норма до 0.5)", "Подключите CDN и кэширование")
            if meta["page_size_kb"] > 500:
                add("performance", 10, "info", "Тяжёлая страница", "HTML больше 500 КБ", "Сожмите HTML, вынесите стили и скрипты")

            sec_headers = {
                "strict-transport-security": "HSTS",
                "x-frame-options": "X-Frame-Options",
                "x-content-type-options": "X-Content-Type-Options",
            }
            for h, name in sec_headers.items():
                if h not in resp.headers:
                    add("security", 10, "warning", f"Нет заголовка {name}", "Сайт уязвим к части атак", f"Добавьте заголовок {name}")
        except Exception:
            html = ""
            add("technical", 40, "critical", "Сайт недоступен", "Не удалось загрузить главную страницу", "Проверьте работу сервера")

        # 5. SEO-разбор страницы
        if html:
            soup = BeautifulSoup(html, "lxml")

            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else ""
            if not title:
                add("seo", 30, "critical", "Нет Title", "Тег title пуст или отсутствует", "Добавьте уникальный title 30-60 символов")
            elif len(title) < 30 or len(title) > 70:
                add("seo", 10, "info", "Неоптимальная длина Title", f"Длина {len(title)} символов", "Оптимально 30-60 символов")

            if not soup.find("h1"):
                add("seo", 20, "warning", "Нет H1", "На странице нет заголовка H1", "Добавьте один H1 с главной темой страницы")

            md = soup.find("meta", attrs={"name": "description"})
            if not md or not (md.get("content") or "").strip():
                add("seo", 20, "warning", "Нет meta description", "Описание страницы отсутствует", "Добавьте description 120-160 символов")

            if not soup.find("link", rel="canonical"):
                add("seo", 10, "info", "Нет canonical", "Возможны дубли страниц", "Добавьте link rel=canonical")

            if not soup.find("meta", attrs={"name": "viewport"}):
                add("seo", 15, "warning", "Нет viewport", "Сайт не адаптирован под мобильные", "Добавьте meta viewport")

            if not soup.find("script", {"type": "application/ld+json"}):
                add("seo", 15, "warning", "Нет schema.org разметки", "AI-системам сложнее понять контент", "Добавьте JSON-LD разметку (FAQ, Article, Organization)")

            if not soup.find("meta", attrs={"property": "og:title"}):
                add("seo", 5, "info", "Нет Open Graph", "Ссылки в соцсетях выглядят блекло", "Добавьте og-теги")

        for k in cat:
            cat[k] = max(0, min(100, cat[k]))

        overall = int(cat["technical"] * 0.25 + cat["security"] * 0.25 + cat["seo"] * 0.3 + cat["performance"] * 0.2)

        return {
            "domain": domain,
            "overall_score": overall,
            "categories": cat,
            "issues": issues,
            "metadata": meta,
            "timestamp": datetime.utcnow().isoformat(),
        }