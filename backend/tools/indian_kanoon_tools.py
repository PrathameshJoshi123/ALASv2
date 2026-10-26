"""
Indian Kanoon Search and Scraping Tool Module.

Provides tools for searching, scraping, and extracting legal provisions,
statutory sections, and court precedents directly from indiankanoon.org.
Uses route-pattern analysis and DuckDuckGo search indexing.
"""

import re
import urllib.parse
import urllib.request
import logging
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# User agent header mimicking a modern browser
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Cache to prevent duplicate network calls across agent invocations
_SEARCH_CACHE: Dict[str, List[Dict[str, Any]]] = {}
_DOC_CACHE: Dict[str, str] = {}
_DOC_META_CACHE: Dict[str, Dict[str, Any]] = {}


def get_cached_doc_meta(doc_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve metadata for a fetched Indian Kanoon document."""
    return _DOC_META_CACHE.get(str(doc_id))


def extract_doc_id(url_or_id: str) -> Optional[str]:
    """
    Extract the numeric document ID from an Indian Kanoon URL or path.
    Examples:
      - 'https://indiankanoon.org/doc/1431516/' -> '1431516'
      - '/docfragment/142628175/?formInput=...' -> '142628175'
      - '1431516' -> '1431516'
    """
    match = re.search(r"/doc(?:fragment)?/(\d+)", url_or_id)
    if match:
        return match.group(1)
    if url_or_id.strip().isdigit():
        return url_or_id.strip()
    return None


def search_via_kanoon_route(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Directly search Indian Kanoon's search engine.
    Indian Kanoon's search returns precise legal statutory and case law articles:
    Pattern: https://indiankanoon.org/search/?formInput={encoded_query}
    """
    results = []
    try:
        clean_query = query.replace("site:indiankanoon.org", "").strip()
        encoded = urllib.parse.quote_plus(clean_query)
        url = f"https://indiankanoon.org/search/?formInput={encoded}"
        
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            soup = BeautifulSoup(html, "html.parser")
            
            seen_ids = set()
            # Indian Kanoon wraps search results in <article class="result">
            articles = soup.find_all("article", class_="result")
            for article in articles:
                rt = article.find(class_="result_title")
                a = rt.find("a", href=True) if rt else article.find("a", href=True)
                if not a:
                    continue
                href = a["href"]
                doc_id = extract_doc_id(href)
                if not doc_id or doc_id in seen_ids:
                    continue
                
                title = a.get_text().strip()
                if not title or title.lower() in {"entire act", "full document", "get in pdf", ""}:
                    continue
                    
                seen_ids.add(doc_id)
                headline = article.find("div", class_="headline")
                snippet = headline.get_text().strip() if headline else ""
                
                results.append({
                    "doc_id": doc_id,
                    "title": title,
                    "url": f"https://indiankanoon.org/doc/{doc_id}/",
                    "snippet": snippet,
                    "source": "Indian Kanoon Direct",
                })
                if len(results) >= max_results:
                    break
    except Exception as e:
        logger.warning(f"Direct Kanoon route search error for query '{query}': {e}")
    return results


def search_via_ddgs(query: str, max_results: int = 4) -> List[Dict[str, Any]]:
    """
    Search using DDGS with backend='yahoo' targeting Indian Kanoon documents.
    Tries site:indiankanoon.org query first, then natural 'indian kanoon <query>'.
    """
    results: List[Dict[str, Any]] = []
    try:
        from ddgs import DDGS
        clean_query = query.replace("site:indiankanoon.org", "").replace("indian kanoon", "").strip()
        # Create concise search terms to avoid Yahoo engine over-filtering
        words = [w for w in re.split(r"\s+", clean_query) if w.isalnum() or "-" in w]
        concise_query = " ".join(words[:6]) if len(words) > 6 else clean_query

        candidates = [
            f"site:indiankanoon.org {concise_query}",
            f"indian kanoon {concise_query}",
            f"site:indiankanoon.org {clean_query}",
        ]

        raw_results: List[Dict[str, Any]] = []
        with DDGS(timeout=10) as ddgs:
            for cand in candidates:
                try:
                    res = list(ddgs.text(cand, backend="yahoo", max_results=max_results * 2))
                    if res:
                        raw_results = res
                        break
                except Exception:
                    continue

        seen_ids = set()
        for item in raw_results:
            href = item.get("href", "")
            doc_id = extract_doc_id(href)
            if doc_id and doc_id not in seen_ids:
                seen_ids.add(doc_id)
                results.append({
                    "doc_id": doc_id,
                    "title": item.get("title", "").replace(" - Indian Kanoon", "").strip(),
                    "url": f"https://indiankanoon.org/doc/{doc_id}/",
                    "snippet": item.get("body", "").strip(),
                    "source": "Yahoo Legal Index (DDGS)",
                })
                if len(results) >= max_results:
                    break
    except Exception as e:
        logger.info(f"DDGS (yahoo) search note for query '{query}': {e}")
    return results


def scrape_kanoon_doc(doc_id: str) -> str:
    """
    Scrape and cleanly extract statutory or judgment text from an Indian Kanoon document page.
    Route pattern: https://indiankanoon.org/doc/{doc_id}/
    """
    if doc_id in _DOC_CACHE:
        return _DOC_CACHE[doc_id]

    url = f"https://indiankanoon.org/doc/{doc_id}/"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            soup = BeautifulSoup(html, "html.parser")
            
            # Decompose ads, scripts, navbars, and promo banners
            for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
                tag.decompose()
            for promo in soup.find_all(class_=lambda c: c and any(x in str(c).lower() for x in ["premium", "ad", "menu", "banner", "sidebar"])):
                promo.decompose()
                
            # Extract document title
            title_node = (
                soup.find("h2", class_="doc_title") or 
                soup.find("div", class_="doc_title") or 
                soup.find("title")
            )
            title = title_node.get_text().strip() if title_node else f"Document ID {doc_id}"
            title = title.replace(" - Indian Kanoon", "").strip()
            
            # Target content containers: akoma-ntoso (statutes), middle_column, judgments, doc
            content_node = (
                soup.find(class_="akoma-ntoso") or
                soup.find("article", class_="middle_column") or
                soup.find("div", class_="judgments") or
                soup.find("div", class_="doc") or
                soup.find("div", class_="maindoc")
            )
            
            if not content_node:
                content_text = soup.get_text()
            else:
                content_text = content_node.get_text()
                
            # Clean up boilerplate text
            lines = []
            for line in content_text.splitlines():
                line = line.strip()
                if not line:
                    continue
                # Skip navigation boilerplate
                if re.match(r"^\[Cites \d+, Cited by \d+\]", line):
                    continue
                if line in {"[Entire Act]", "Get in PDF", "Print it!", "Take notes as you read"}:
                    continue
                lines.append(line)
                
            cleaned_body = "\n".join(lines)
            
            # Format output with header and up to 3500 characters of substantive legal text
            formatted_output = (
                f"### [Indian Kanoon: {title}]\n"
                f"URL: {url}\n\n"
                f"{cleaned_body[:3500]}"
            )
            if len(cleaned_body) > 3500:
                formatted_output += "\n\n... [Content truncated for context window; substantive provisions captured above] ..."
                
            _DOC_CACHE[doc_id] = formatted_output
            _DOC_META_CACHE[doc_id] = {
                "doc_id": doc_id,
                "title": title,
                "url": url,
                "statute_or_court": "Indian Statute / Precedent" if "section" in title.lower() or "act" in title.lower() else "High Court / Supreme Court",
                "summary": cleaned_body[:300].strip(),
            }
            return formatted_output
            
    except Exception as e:
        err_msg = f"Failed to retrieve Indian Kanoon document {doc_id} from {url}: {e}"
        logger.error(err_msg)
        return err_msg


def search_indian_kanoon_raw(query: str, max_results: int = 4) -> str:
    """
    Internal search function executing BOTH direct Indian Kanoon search and
    Yahoo legal search (via DDGS) concurrently, returning a deduplicated,
    blended list of legal authorities.
    """
    cache_key = f"{query.strip().lower()}_{max_results}"
    if cache_key in _SEARCH_CACHE:
        results = _SEARCH_CACHE[cache_key]
    else:
        # Run both direct Kanoon search and Yahoo (DDGS) search
        kanoon_results = search_via_kanoon_route(query, max_results=max_results)
        ddgs_results = search_via_ddgs(query, max_results=max_results)

        # Merge results with Kanoon direct + Yahoo DDGS, deduplicating by doc_id
        results: List[Dict[str, Any]] = []
        seen_ids = set()

        for r in kanoon_results:
            if r["doc_id"] not in seen_ids:
                seen_ids.add(r["doc_id"])
                results.append(r)

        for dr in ddgs_results:
            if dr["doc_id"] not in seen_ids:
                seen_ids.add(dr["doc_id"])
                results.append(dr)

        _SEARCH_CACHE[cache_key] = results

    if not results:
        return f"No Indian Kanoon documents found matching query: '{query}'."

    formatted = [f"Found {len(results)} relevant Indian Kanoon documents for query '{query}':\n"]
    for i, res in enumerate(results[:max_results * 2], 1):
        formatted.append(
            f"{i}. **{res['title']}**\n"
            f"   - Doc ID: `{res['doc_id']}`\n"
            f"   - URL: {res['url']}\n"
            f"   - Source Engine: {res.get('source', 'Indian Kanoon')}\n"
            f"   - Excerpt: {res['snippet'][:250]}"
        )
    formatted.append("\nTip: Call `fetch_kanoon_document` with any Doc ID or URL above to inspect the full statutory section or judgment.")
    return "\n".join(formatted)


@tool
def search_indian_kanoon(query: str, max_results: int = 4) -> str:
    """
    Search Indian Kanoon (indiankanoon.org) for Indian laws, statutory sections,
    and court judgments.
    """
    return search_indian_kanoon_raw(query=query, max_results=max_results)


def fetch_kanoon_document_raw(doc_id_or_url: str) -> str:
    """Internal fetch function returning scraped document text."""
    doc_id = extract_doc_id(doc_id_or_url)
    if not doc_id:
        return f"Invalid Indian Kanoon document ID or URL format: '{doc_id_or_url}'. Expected numeric ID or URL like 'https://indiankanoon.org/doc/1431516/'."
    return scrape_kanoon_doc(doc_id)


@tool
def fetch_kanoon_document(doc_id_or_url: str) -> str:
    """
    Retrieve and read the statutory provisions or judgment text of a document from Indian Kanoon.
    """
    return fetch_kanoon_document_raw(doc_id_or_url=doc_id_or_url)



