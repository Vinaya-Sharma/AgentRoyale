from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass

from backend.models import Task


@dataclass(frozen=True)
class ExtractedTruth:
    value: str
    evidence: str
    confidence: str = "high"
    notes: str = "Extracted with deterministic source-specific parser."


def extract_ground_truth(task: Task, page_text: str) -> ExtractedTruth | None:
    text = html.unescape(page_text or "")
    extractors = [
        extract_npm_downloads,
        extract_github_repo_metric,
        extract_package_or_runtime_version,
        extract_hacker_news,
        extract_app_store,
        extract_companies_market_cap,
        extract_coinmarketcap_price,
        extract_xe_rate,
        extract_amazon_current_price,
        extract_structured_bright_data,
        extract_linkedin_company_metric,
        extract_apple_macbook_air_price,
        extract_apple_iphone16_price,
        extract_samsung_phone_price,
        extract_common_price_or_rate,
    ]
    for extractor in extractors:
        result = extractor(task, text)
        if result:
            return result
    return None


def clean_value(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def clean_evidence(value: str) -> str:
    return clean_value(re.sub(r"<[^>]+>", " ", value))


def extract_npm_downloads(task: Task, text: str) -> ExtractedTruth | None:
    if "npmjs.com/package" not in task.canonical_url or "weekly downloads" not in task.extract_field.lower():
        return None
    match = re.search(r"Weekly Downloads\s+([0-9][0-9,]+)", text, re.I)
    if not match:
        return None
    value = match.group(1).replace(",", "")
    return ExtractedTruth(value=value, evidence=clean_evidence(match.group(0)))


def extract_github_repo_metric(task: Task, text: str) -> ExtractedTruth | None:
    if "github.com/" not in task.canonical_url:
        return None
    field = task.extract_field.lower()
    if "star" in field:
        patterns = [
            r"Star\s+([0-9.]+[kKmMbB]?)",
            r"([0-9.]+[kKmMbB]?)\s+stars",
        ]
    elif "open issue" in field:
        patterns = [
            r"\[Issues\s+([0-9.]+[kKmMbB]?)\]",
            r"([0-9.]+[kKmMbB]?)\s+Open",
        ]
    else:
        return None
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return ExtractedTruth(value=match.group(1), evidence=clean_evidence(match.group(0)))
    return None


def extract_package_or_runtime_version(task: Task, text: str) -> ExtractedTruth | None:
    field = task.extract_field.lower()
    url = task.canonical_url
    if "latest version" in field and "pypi.org/project" in url:
        name = url.rstrip("/").split("/")[-1]
        match = re.search(rf"\b{re.escape(name)}\s+([0-9]+(?:\.[0-9]+)+[a-z0-9.-]*)", text, re.I)
        if match:
            return ExtractedTruth(value=match.group(1), evidence=clean_evidence(match.group(0)))
    if "latest stable" in field and "nodejs.org" in url:
        match = re.search(r"(v[0-9]+(?:\.[0-9]+)+)\s*Current", text, re.I)
        if match:
            return ExtractedTruth(value=match.group(1), evidence=clean_evidence(match.group(0)))
    if "latest stable" in field and "python.org/downloads" in url:
        match = re.search(r"Python\s+([0-9]+(?:\.[0-9]+)+)", text, re.I)
        if match:
            return ExtractedTruth(value=match.group(1), evidence=clean_evidence(match.group(0)))
    return None


def extract_hacker_news(task: Task, text: str) -> ExtractedTruth | None:
    if "news.ycombinator.com" not in task.canonical_url:
        return None
    story_text = text.split("[login]", 1)[-1]
    if "top story title" in task.extract_field.lower():
        for match in re.finditer(r"\[([^\]\n]+)\]\(([^)]+)\)", story_text):
            title = clean_value(match.group(1))
            url = match.group(2)
            if not title or re.fullmatch(r"\d+\s+(?:minute|minutes|hour|hours|day|days)\s+ago", title, re.I):
                continue
            if title.lower() in {"comments", "discuss", "hide", "past", "more"}:
                continue
            if title.lower() == "hacker news" or url in {"news", "newest", "front"}:
                continue
            if url.startswith("user?id=") or url.startswith("from?") or "item?id=" in url:
                continue
            return ExtractedTruth(value=title, evidence=clean_evidence(match.group(0)))
    if "top story points" in task.extract_field.lower():
        match = re.search(r"([0-9]+)\s+points\s+by", story_text, re.I)
        if match:
            return ExtractedTruth(value=match.group(1), evidence=clean_evidence(match.group(0)))
    return None


def extract_app_store(task: Task, text: str) -> ExtractedTruth | None:
    if "apps.apple.com" not in task.canonical_url:
        return None
    field = task.extract_field.lower()
    if "rating" in field:
        match = re.search(r"([0-5](?:\.[0-9])?)\s*out of 5", text, re.I)
        if match:
            return ExtractedTruth(value=match.group(1), evidence=clean_evidence(match.group(0)))
    if "version" in field:
        match = re.search(r"Version\s+([0-9]+(?:\.[0-9]+)+)", text, re.I)
        if match:
            return ExtractedTruth(value=match.group(1), evidence=clean_evidence(match.group(0)))
    return None


def extract_companies_market_cap(task: Task, text: str) -> ExtractedTruth | None:
    if "companiesmarketcap.com" not in task.canonical_url:
        return None
    match = re.search(r"Market cap:\s*\$?\s*([0-9.]+\s*(?:Trillion|Billion|T|B|M)?)", text, re.I)
    if match:
        return ExtractedTruth(value=match.group(1), evidence=clean_evidence(match.group(0)))
    return None


def extract_coinmarketcap_price(task: Task, text: str) -> ExtractedTruth | None:
    if "coinmarketcap.com/currencies" not in task.canonical_url:
        return None
    matches = list(re.finditer(r"\$([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:USD)?", text, re.I))
    for match in matches:
        number = match.group(1).replace(",", "")
        try:
            value = float(number)
        except ValueError:
            continue
        if value < 10:
            continue
        start = max(0, match.start() - 80)
        end = min(len(text), match.end() + 80)
        return ExtractedTruth(value=f"${match.group(1)}", evidence=clean_evidence(text[start:end]))
    return None


def extract_xe_rate(task: Task, text: str) -> ExtractedTruth | None:
    if "xe.com/currencyconverter" not in task.canonical_url:
        return None
    match = re.search(r"1(?:\.00)?\s+EUR\s*=\s*([0-9.]+)\s+USD", text, re.I)
    if match:
        return ExtractedTruth(value=match.group(1), evidence=clean_evidence(match.group(0)))
    return None


def extract_amazon_current_price(task: Task, text: str) -> ExtractedTruth | None:
    if "amazon.com" not in task.canonical_url:
        return None
    if "current amazon price" not in task.extract_field.lower() and "current price" not in task.question.lower():
        return None
    patterns = [
        r"Buy New\s+(\$[0-9][0-9,]*(?:\.[0-9]{2})?)",
        r"(\$[0-9][0-9,]*(?:\.[0-9]{2})?)\s+with\s+[0-9]+\s+percent\s+savings",
        r"priceToPay[\s\S]{0,120}?(\$[0-9][0-9,]*(?:\.[0-9]{2})?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        price = match.group(1)
        evidence = clean_evidence(text[max(0, match.start() - 80): min(len(text), match.end() + 160)])
        if "list price" in evidence.lower() and "buy new" not in evidence.lower() and "savings" not in evidence.lower():
            continue
        return ExtractedTruth(
            value=price,
            evidence=evidence,
            notes="Extracted Amazon current buy/new price; list price/MSRP is ignored when both appear.",
        )
    return None


def parse_structured_records(text: str) -> list[dict]:
    raw = text.strip()
    if not raw.startswith(("[", "{")):
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, dict):
        return [parsed]
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    return []


def clean_integer_field(value: object) -> str | None:
    cleaned = re.sub(r"[^0-9]", "", str(value or ""))
    return cleaned or None


def clean_number_field(value: object) -> str | None:
    match = re.search(r"[0-9][0-9,]*(?:\.[0-9]+)?", str(value or ""))
    return match.group(0).replace(",", "") if match else None


def first_present(record: dict, keys: tuple[str, ...]) -> tuple[str, object] | None:
    for key in keys:
        value = record.get(key)
        if value not in (None, "", [], {}):
            return key, value
    return None


def extract_structured_bright_data(task: Task, text: str) -> ExtractedTruth | None:
    records = parse_structured_records(text)
    if not records:
        return None
    record = records[0]
    field = task.extract_field.lower()

    if task.bd_tool == "web_data_linkedin_company_profile":
        if "employees_in_linkedin" in field and record.get("employees_in_linkedin") is not None:
            value = clean_integer_field(record["employees_in_linkedin"])
            if not value:
                return None
            return ExtractedTruth(
                value=value,
                evidence=f'"employees_in_linkedin":{value}',
                notes="Extracted structured LinkedIn employees_in_linkedin field from Bright Data.",
            )
        if "followers" in field and record.get("followers") is not None:
            value = clean_integer_field(record["followers"])
            if not value:
                return None
            return ExtractedTruth(
                value=value,
                evidence=f'"followers":{value}',
                notes="Extracted structured LinkedIn followers field from Bright Data.",
            )

    if task.bd_tool == "web_data_linkedin_job_listings":
        title = record.get("title") or record.get("job_title") or record.get("position")
        if title:
            return ExtractedTruth(
                value=clean_value(str(title)),
                evidence=f'"title":"{clean_value(str(title))}"',
                notes="Extracted first structured LinkedIn job listing title from Bright Data.",
            )

    if task.bd_tool in {"web_data_apple_app_store", "web_data_google_play_store"}:
        if "rating" in field:
            found = first_present(record, ("rating", "score", "average_rating", "stars"))
            if found:
                key, raw = found
                value = clean_number_field(raw)
                if value:
                    return ExtractedTruth(
                        value=value,
                        evidence=f'"{key}":{raw}',
                        notes=f"Extracted structured {key} rating field from Bright Data app-store data.",
                    )
        if "version" in field:
            found = first_present(record, ("version", "current_version", "app_version"))
            if found:
                key, raw = found
                value = clean_value(str(raw))
                return ExtractedTruth(
                    value=value,
                    evidence=f'"{key}":"{value}"',
                    notes=f"Extracted structured {key} version field from Bright Data app-store data.",
                )

    if task.bd_tool == "web_data_youtube_profiles":
        if "subscriber" in field:
            found = first_present(record, ("subscribers", "subscribers_count", "subscriber_count"))
            if found:
                key, raw = found
                value = clean_integer_field(raw)
                if value:
                    return ExtractedTruth(
                        value=value,
                        evidence=f'"{key}":{value}',
                        notes="Extracted structured YouTube subscriber count from Bright Data.",
                    )

    if task.bd_tool == "web_data_github_repository_file":
        code = record.get("code")
        if isinstance(code, list):
            joined = "\n".join(str(line) for line in code)
            match = re.search(r'"version"\s*:\s*"([^"]+)"', joined)
            if match:
                return ExtractedTruth(
                    value=match.group(1),
                    evidence=clean_evidence(match.group(0)),
                    notes="Extracted version field from structured Bright Data GitHub repository file content.",
                )

    if task.bd_tool in {"web_data_bestbuy_products", "web_data_walmart_product", "web_data_ebay_product"}:
        if "price" in field:
            found = first_present(record, ("final_price", "sale_price", "price", "current_price"))
            if found:
                key, raw = found
                value = clean_number_field(raw)
                if value:
                    return ExtractedTruth(
                        value=f"${float(value):,.2f}",
                        evidence=f'"{key}":{raw}',
                        notes=f"Extracted structured {key} price field from Bright Data product data.",
                    )

    if task.bd_tool == "web_data_amazon_product" and "price" in field:
        found = first_present(record, ("final_price", "buybox_price", "price", "current_price", "deal_price"))
        if found:
            key, raw = found
            value = clean_number_field(raw)
            if value:
                return ExtractedTruth(
                    value=f"${float(value):,.2f}",
                    evidence=f'"{key}":{raw}',
                    notes=f"Extracted structured {key} price field from Bright Data Amazon product data.",
                )

    return None


def extract_linkedin_company_metric(task: Task, text: str) -> ExtractedTruth | None:
    if "linkedin.com/company" not in task.canonical_url:
        return None
    field = task.extract_field.lower()
    if "follower" in field:
        match = re.search(r"([0-9][0-9,]+)\s+followers", text, re.I)
        if match:
            return ExtractedTruth(value=match.group(1).replace(",", ""), evidence=clean_evidence(match.group(0)))
    if "employee" in field:
        match = re.search(r"Company size\s+([0-9,]+-[0-9,]+\s+employees)", text, re.I)
        if match:
            return ExtractedTruth(value=match.group(1), evidence=clean_evidence(match.group(0)))
    return None


def extract_apple_macbook_air_price(task: Task, text: str) -> ExtractedTruth | None:
    if "apple.com/shop/buy-mac/macbook-air" not in task.canonical_url:
        return None
    question = task.question.lower()
    if "15" not in question or "macbook air" not in question:
        return None
    structured_match = re.search(
        r'"name"\s*:\s*"15-inch MacBook Air"[\s\S]{0,1200}?"lowPrice"\s*:\s*([0-9]+(?:\.[0-9]+)?)',
        text,
        re.I,
    )
    if structured_match:
        raw_price = structured_match.group(1)
        display = f"${float(raw_price):,.0f}" if raw_price.endswith(".00") else f"${float(raw_price):,.2f}"
        return ExtractedTruth(
            value=display,
            evidence=clean_evidence(structured_match.group(0))[:500],
            notes="Extracted Apple 15-inch MacBook Air base starting price from official Apple structured product data.",
        )
    patterns = [
        r"(?:15-inch|15‑inch|15\.3-inch|15 inch)[\s\S]{0,500}?(?:from|starts at|starting at)?\s*(\$1,299|\$1299(?:\.00)?)",
        r"(?:from|starts at|starting at)\s*(\$1,299|\$1299(?:\.00)?)[\s\S]{0,500}?(?:15-inch|15‑inch|15\.3-inch|15 inch)",
        r"MacBook Air[\s\S]{0,800}(?:15-inch|15‑inch|15\.3-inch|15 inch)[\s\S]{0,800}(\$1,299|\$1299(?:\.00)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            start = max(0, match.start() - 100)
            end = min(len(text), match.end() + 140)
            return ExtractedTruth(
                value=match.group(1),
                evidence=clean_evidence(text[start:end]),
                notes="Extracted Apple 15-inch MacBook Air base starting price from the official Apple buy page.",
            )
    if "$1,299" in text or "$1299" in text:
        price = "$1,299" if "$1,299" in text else "$1299"
        idx = text.find(price)
        return ExtractedTruth(
            value=price,
            evidence=clean_evidence(text[max(0, idx - 160): idx + 160]),
            notes="Extracted Apple 15-inch MacBook Air price from the official Apple buy page.",
        )
    return None


def extract_apple_iphone16_price(task: Task, text: str) -> ExtractedTruth | None:
    if "apple.com/shop/buy-iphone/iphone-16" not in task.canonical_url:
        return None
    if "iphone 16" not in task.question.lower() or "cheapest" not in task.question.lower():
        return None

    haystack = text[:60000]
    structured_match = re.search(
        r'"@type"\s*:\s*"AggregateOffer"\s*,\s*"lowPrice"\s*:\s*([0-9]+(?:\.[0-9]+)?)'
        r'\s*,\s*"highPrice"\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*,\s*"priceCurrency"\s*:\s*"USD"',
        haystack,
        re.I,
    )
    if structured_match:
        raw_price = float(structured_match.group(1))
        return ExtractedTruth(
            value=f"${raw_price:,.2f}",
            evidence=clean_evidence(structured_match.group(0)),
            notes=(
                "Extracted Apple's structured AggregateOffer lowPrice for the new iPhone 16; "
                "this represents the lowest Apple-listed device price and excludes trade-in/bill-credit math."
            ),
        )

    base_match = re.search(
        r"\[\s*128GB\s+Footnote\s+1[\s\S]{0,140}?Connect to any carrier later\s+"
        r"(\$[0-9][0-9,]*(?:\.[0-9]{2})?)\s*\]"
        r"\\?\(https://www\.apple\.com/shop/buy-iphone/iphone-16/6\.1-inch-display-128gb-[^)]+-unlocked\\?\)",
        haystack,
        re.I,
    )
    if not base_match:
        base_match = re.search(
            r"iPhone 16[\s\S]{0,12000}?128GB[\s\S]{0,220}?Connect to any carrier later\s+"
            r"(\$[0-9][0-9,]*(?:\.[0-9]{2})?)[\s\S]{0,180}?6\.1-inch-display-128gb",
            haystack,
            re.I,
        )
    if not base_match:
        return None

    base_price = float(base_match.group(1).replace("$", "").replace(",", ""))
    discount_match = re.search(
        r"Pricing for iPhone 16 and 16 Plus includes a\s+\$([0-9]+(?:\.[0-9]{2})?)",
        haystack,
        re.I,
    )

    if discount_match:
        discount = float(discount_match.group(1))
        value = f"${base_price - discount:,.2f}"
        sentence_end = haystack.find(".", discount_match.start())
        discount_evidence = haystack[discount_match.start(): sentence_end + 1 if sentence_end != -1 else discount_match.end()]
        evidence = clean_evidence(f"{base_match.group(0)}. {discount_evidence}")
        notes = (
            "Computed the lowest Apple-listed new iPhone 16 price from Apple's connect-later "
            "price minus Apple's instant carrier activation discount; trade-in credits, bill "
            "credits, installments, and other iPhone models are ignored."
        )
        return ExtractedTruth(value=value, evidence=evidence, notes=notes)

    return ExtractedTruth(
        value=f"${base_price:,.2f}",
        evidence=clean_evidence(base_match.group(0)),
        notes="Extracted Apple connect-later iPhone 16 price; no instant carrier activation discount was found in the fetched page.",
    )


def extract_samsung_phone_price(task: Task, text: str) -> ExtractedTruth | None:
    if "samsung.com/us/smartphones/galaxy-s25-ultra" not in task.canonical_url:
        return None
    if "256gb" not in task.question.lower() and "256gb" not in task.canonical_url.lower():
        return None
    lowered = text.lower()
    if "1tb" in lowered[:1200] and "256gb" not in lowered[:1200]:
        return None
    patterns = [
        r"One-time Payment\s*(?:\n|\s)+(\$[0-9][0-9,]*(?:\.[0-9]{2})?)",
        r"was:\s*\$[0-9][0-9,]*(?:\.[0-9]{2})?\s*(\$[0-9][0-9,]*(?:\.[0-9]{2})?)",
        r"256GB[\s\S]{0,220}?was:\s*\$[0-9][0-9,]*(?:\.[0-9]{2})?\s*(\$[0-9][0-9,]*(?:\.[0-9]{2})?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            evidence_start = max(0, match.start() - 80)
            evidence_end = min(len(text), match.end() + 120)
            return ExtractedTruth(
                value=match.group(1),
                evidence=clean_evidence(text[evidence_start:evidence_end]),
                notes="Extracted current 256GB Samsung selling price, not MSRP.",
            )
    return None


def extract_common_price_or_rate(task: Task, text: str) -> ExtractedTruth | None:
    field = task.extract_field.lower()
    notes = task.grading_notes.lower()
    haystack = text[:40000]
    if "netflix" in task.question.lower() and "standard with ads" in notes:
        match = re.search(r"Standard with ads:\s*(\$[0-9]+(?:\.[0-9]{2})?)\s*/\s*month", haystack, re.I)
        if match:
            return ExtractedTruth(value=match.group(1), evidence=clean_evidence(match.group(0)))
    if "spotify" in task.question.lower() and "individual" in notes:
        match = re.search(r"\$([0-9]+(?:\.[0-9]{2})?)\s+per month", haystack, re.I)
        if match:
            return ExtractedTruth(value=f"${match.group(1)}", evidence=clean_evidence(match.group(0)))
    if "30-year fixed" in field or "mortgage" in task.question.lower():
        match = re.search(r"30-year fixed-rate mortgage averaged\s+([0-9.]+%)", haystack, re.I)
        if match:
            return ExtractedTruth(value=match.group(1), evidence=clean_evidence(match.group(0)))
    if "federal funds" in task.question.lower():
        match = re.search(r"([0-9.]+%\s*(?:to|-)\s*[0-9.]+%)", haystack, re.I)
        if match:
            return ExtractedTruth(value=match.group(1), evidence=clean_evidence(match.group(0)))
    if "minimum wage" in task.question.lower():
        match = re.search(r"\$7\.25\s+per hour", haystack, re.I)
        if match:
            return ExtractedTruth(value="$7.25", evidence=clean_evidence(match.group(0)))
    if "passport book" in task.question.lower():
        match = re.search(r"(?:Adult.*?Renewal.*?|Passport Book.*?)(\$[0-9]+)", haystack, re.I | re.S)
        if match:
            return ExtractedTruth(value=match.group(1), evidence=clean_evidence(match.group(0))[:240])
    if "price" in field or "monthly price" in field:
        dollar_values = re.findall(r"\$[0-9][0-9,]*(?:\.[0-9]{2})?", haystack)
        if len(dollar_values) == 1:
            value = dollar_values[0]
            return ExtractedTruth(value=value, evidence=value)
    return None
