import time
import socket
import ssl
import re
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
            add("technical", 40, "critical", "DNS не найден", "Домен не имеет A-записи и не открывается", "Проверьте настройки DNS у регистратора домена")

        # 2. Возраст домена
        try:
            import whois
            w = whois.whois(domain)
            created = w.creation_date
            if isinstance(created, list):
                created = created[0] if created else None
            if created:
                age = (datetime.utcnow() - created).days
                meta["domain_age_days"] = age
                if age < 180:
                    add("technical", 15, "warning", "Очень молодой домен", f"Домену всего {age} дней", "AI и поисковики меньше доверяют новым доменам. Наращивайте историю и контент")
                elif age < 365:
                    add("technical", 8, "info", "Молодой домен", f"Домену {age} дней", "Старые домены ранжируются лучше — продолжайте развивать сайт")
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
                    issuer = dict(x[0] for x in cert.get("issuer", []))
                    meta["ssl_days_left"] = days_left
                    meta["ssl_issuer"] = issuer.get("organizationName", "")
                    if days_left < 0:
                        add("security", 50, "critical", "SSL-сертификат просрочен", "Сертификат истёк — браузеры показывают предупреждение", "Срочно обновите сертификат")
                    elif days_left < 14:
                        add("security", 20, "warning", "SSL скоро истечёт", f"Осталось {days_left} дней", "Продлите сертификат заранее")
        except Exception:
            add("security", 50, "critical", "Нет HTTPS", "Сайт не работает по защищённому протоколу", "Установите бесплатный сертификат Let's Encrypt — это обязательно для SEO и доверия")

        # 4. Загрузка страницы
        html = ""
        resp_headers = {}
        try:
            t0 = time.time()
            async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=HEADERS) as client:
                resp = await client.get(f"https://{domain}")
                ttfb = round(time.time() - t0, 2)
                html = resp.text
                resp_headers = {k.lower(): v for k, v in resp.headers.items()}
                meta["ttfb_sec"] = ttfb
                meta["http_status"] = resp.status_code
                meta["page_size_kb"] = round(len(html) / 1024, 1)
                meta["server"] = resp.headers.get("server", "")

            if resp.status_code >= 400:
                add("technical", 30, "critical", f"Ошибка HTTP {resp.status_code}", "Главная страница отдаёт ошибку сервера", "Исправьте ошибку — поисковики и AI не индексируют сломанные страницы")
            if ttfb > 3:
                add("performance", 35, "critical", "Очень медленный сервер", f"Время ответа {ttfb} сек (норма до 0.5 сек)", "Подключите CDN (Cloudflare бесплатно), включите кэширование, оптимизируйте базу данных")
            elif ttfb > 1:
                add("performance", 20, "warning", "Медленный ответ сервера", f"Время ответа {ttfb} сек", "Ускорьте сервер: кэширование, CDN, оптимизация запросов")
            if meta["page_size_kb"] > 1000:
                add("performance", 20, "warning", "Очень тяжёлая страница", f"HTML весит {meta['page_size_kb']} КБ", "Сожмите HTML, минифицируйте CSS/JS, используйте lazy loading для картинок")
            elif meta["page_size_kb"] > 500:
                add("performance", 10, "info", "Страница тяжеловата", f"HTML {meta['page_size_kb']} КБ", "Оптимизируйте размер страницы для скорости")

            # Заголовки безопасности
            sec_checks = [
                ("strict-transport-security", "HSTS", "Защищает от понижения до HTTP"),
                ("x-frame-options", "X-Frame-Options", "Защищает от кликджекинга"),
                ("x-content-type-options", "X-Content-Type-Options", "Защищает от подделки MIME-типов"),
                ("content-security-policy", "Content-Security-Policy", "Защищает от XSS-атак"),
                ("referrer-policy", "Referrer-Policy", "Контролирует утечку referrer"),
            ]
            missing_sec = []
            for h, name, why in sec_checks:
                if h not in resp_headers:
                    missing_sec.append(name)
                    add("security", 8, "warning", f"Нет заголовка {name}", why, f"Добавьте заголовок {name} в настройках сервера")
            meta["missing_security_headers"] = missing_sec

            # Сжатие
            if "gzip" not in resp_headers.get("content-encoding", "") and "br" not in resp_headers.get("content-encoding", ""):
                add("performance", 10, "info", "Нет сжатия", "Страница передаётся без gzip/brotli", "Включите gzip или brotli на сервере — страницы станут легче в 3-5 раз")

        except Exception:
            add("technical", 40, "critical", "Сайт недоступен", "Не удалось загрузить главную страницу по HTTPS", "Проверьте, что сервер работает и SSL настроен")

        # 5. SEO-анализ
        if html:
            soup = BeautifulSoup(html, "lxml")

            # Title
            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else ""
            meta["title"] = title[:100]
            if not title:
                add("seo", 30, "critical", "Нет Title", "Тег title пуст или отсутствует — это главный сигнал для поисковиков и AI", "Добавьте уникальный title 30-60 символов с ключевыми словами")
            elif len(title) < 30:
                add("seo", 12, "warning", "Слишком короткий Title", f"Длина всего {len(title)} символов", "Расширьте title до 30-60 символов, добавьте ключевые слова")
            elif len(title) > 70:
                add("seo", 8, "info", "Слишком длинный Title", f"Длина {len(title)} символов — обрезается в выдаче", "Сократите title до 60 символов")

            # H1
            h1_tags = soup.find_all("h1")
            meta["h1_count"] = len(h1_tags)
            if not h1_tags:
                add("seo", 20, "warning", "Нет заголовка H1", "На странице нет H1 — поисковикам непонятна главная тема", "Добавьте один H1 с основной темой страницы")
            elif len(h1_tags) > 1:
                add("seo", 10, "info", "Несколько H1", f"Найдено {len(h1_tags)} заголовков H1", "Оставьте только один H1 на странице")

            # Meta description
            md = soup.find("meta", attrs={"name": "description"})
            desc = (md.get("content") or "").strip() if md else ""
            meta["has_description"] = bool(desc)
            if not desc:
                add("seo", 20, "warning", "Нет meta description", "Описание отсутствует — сниппет в выдаче формируется случайно", "Добавьте привлекательное description 120-160 символов")
            elif len(desc) < 100 or len(desc) > 170:
                add("seo", 6, "info", "Неоптимальное description", f"Длина {len(desc)} символов", "Оптимально 120-160 символов")

            # Canonical
            if not soup.find("link", rel="canonical"):
                add("seo", 10, "info", "Нет canonical", "Без canonical возможны дубли страниц в индексе", "Добавьте <link rel=canonical> с основным URL страницы")

            # Viewport (мобильность)
            if not soup.find("meta", attrs={"name": "viewport"}):
                add("seo", 18, "warning", "Не адаптирован под мобильные", "Нет meta viewport — сайт плохо выглядит на телефонах", "Добавьте <meta name=viewport content='width=device-width, initial-scale=1'>")

            # Schema.org (важно для AI!)
            schemas = soup.find_all("script", {"type": "application/ld+json"})
            meta["schema_count"] = len(schemas)
            if not schemas:
                add("seo", 20, "warning", "Нет schema.org разметки", "Без структурированных данных AI-системам сложно понять ваш контент — это напрямую влияет на цитируемость", "Добавьте JSON-LD разметку: Organization, FAQPage, Article. Это самый важный фактор для GEO")

            # Open Graph
            if not soup.find("meta", attrs={"property": "og:title"}):
                add("seo", 6, "info", "Нет Open Graph", "Ссылки в соцсетях и мессенджерах выглядят блекло", "Добавьте og:title, og:description, og:image")

            # Favicon
            if not soup.find("link", rel=re.compile("icon")):
                add("seo", 4, "info", "Нет favicon", "Сайт без иконки выглядит непрофессионально", "Добавьте favicon.ico")

            # Количество слов (тонкий контент)
            text = soup.get_text(separator=" ", strip=True)
            words = len(text.split())
            meta["word_count"] = words
            if words < 150:
                add("seo", 15, "warning", "Мало текста на странице", f"Всего {words} слов — слишком тонкий контент", "AI и поисковики ценят подробный контент. Добавьте полезный текст (300+ слов)")

            # Внутренние ссылки
            internal_links = len([a for a in soup.find_all("a", href=True) if a["href"].startswith("/")])
            meta["internal_links"] = internal_links
            if internal_links < 3:
                add("seo", 8, "info", "Мало внутренних ссылок", f"Всего {internal_links} внутренних ссылок", "Добавьте перелинковку между страницами — это помогает индексации")

            # Картинки без alt
            imgs = soup.find_all("img")
            no_alt = sum(1 for img in imgs if not img.get("alt"))
            meta["images_total"] = len(imgs)
            meta["images_no_alt"] = no_alt
            if imgs and no_alt > len(imgs) / 2:
                add("seo", 8, "info", "Картинки без alt", f"{no_alt} из {len(imgs)} картинок без описания", "Добавьте alt-текст к картинкам — это помогает SEO и доступности")

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
