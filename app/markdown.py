import re
from bs4 import BeautifulSoup
import markdownify


_REMOVE_TAGS = ["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"]

_AD_CLASS_PATTERNS = re.compile(
    r"\b(ad|ads|advert|advertisement|banner|promo|sidebar|widget|cookie|popup|modal|overlay)\b",
    re.IGNORECASE,
)


def _remove_noise(soup: BeautifulSoup) -> None:
    for tag in _REMOVE_TAGS:
        for el in soup.find_all(tag):
            el.decompose()

    for el in soup.find_all(True):
        classes = " ".join(el.get("class", []))
        ids = el.get("id", "")
        if _AD_CLASS_PATTERNS.search(classes) or _AD_CLASS_PATTERNS.search(ids):
            el.decompose()


def _find_main_content(soup: BeautifulSoup) -> BeautifulSoup:
    for selector in ["main", "article", '[role="main"]']:
        el = soup.select_one(selector)
        if el:
            return el

    # Fall back to the largest block-level element by text length
    candidates = soup.find_all(["div", "section"])
    if candidates:
        return max(candidates, key=lambda el: len(el.get_text()))

    return soup.body or soup


def clean_html(raw_html: str, only_main_content: bool = True) -> tuple[str, str]:
    """Return (cleaned_html, markdown)."""
    soup = BeautifulSoup(raw_html, "html.parser")
    _remove_noise(soup)

    root = _find_main_content(soup) if only_main_content else (soup.body or soup)

    cleaned_html = str(root)

    md = markdownify.markdownify(cleaned_html, heading_style="ATX", strip=["a"] if False else [])
    # Collapse 3+ consecutive blank lines into 2
    md = re.sub(r"\n{3,}", "\n\n", md).strip()

    return cleaned_html, md
