"""Scraper for richbourse.com mouvement/chart page – extract data from div.panel.

Target URL: https://www.richbourse.com/common/mouvements/index/{symbol}
Example: https://www.richbourse.com/common/mouvements/index/NTLC
Page: "Analyse graphique" – find div with class="panel" and extract their content.
"""
import re
import logging
from typing import Any

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper
import config

logger = logging.getLogger(__name__)

RICHBOURSE_MOUVEMENTS_BASE = "https://www.richbourse.com/common/mouvements/index"


def _normalize_num(s: str) -> str:
    return re.sub(r"\s", "", str(s).strip()).replace("\xa0", "") if s else ""


def _parse_int(s: str) -> int | None:
    n = _normalize_num(s)
    return int(n) if n.isdigit() else None


def _parse_float(s: str) -> float | None:
    s = (s or "").replace(",", ".").replace("%", "").strip()
    s = _normalize_num(s)
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _table_to_list(table) -> list[list[str]]:
    """Convert a <table> into a list of rows (each row = list of cell texts)."""
    if not table or table.name != "table":
        return []
    rows = []
    for tr in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if cells:
            rows.append(cells)
    return rows


def _table_to_dict(rows: list[list[str]]) -> dict[str, Any]:
    """Convert two-column table rows into key-value dict (e.g. 'Volume (titres)' -> '482')."""
    out: dict[str, Any] = {}
    for row in rows:
        if len(row) >= 2:
            key = row[0].strip()
            val = row[1].strip()
            n = _normalize_num(val)
            if n.isdigit():
                out[key] = int(n)
            elif n.replace(".", "").replace("-", "").isdigit() or (n and n[0] == "-" and n[1:].replace(".", "").isdigit()):
                try:
                    out[key] = float(val.replace(",", ".").replace(" ", ""))
                except ValueError:
                    out[key] = val
            else:
                out[key] = val
        elif len(row) == 1 and row[0].strip():
            out["_"] = row[0].strip()
    return out


def _extract_panel_data(panel) -> dict[str, Any]:
    """Extract title, body text, and tables from a div.panel."""
    data: dict[str, Any] = {"title": None, "content": "", "tables": []}
    title_el = panel.find(class_=re.compile(r"panel-title|panel-heading"))
    if title_el:
        data["title"] = title_el.get_text(strip=True)
    body = panel.find(class_=re.compile(r"panel-body|panel-content")) or panel
    text_parts = []
    for table in body.find_all("table"):
        rows = _table_to_list(table)
        if rows:
            data["tables"].append({"rows": rows, "key_value": _table_to_dict(rows) if all(len(r) >= 2 for r in rows if len(r) >= 1) else None})
        table.decompose()
    data["content"] = body.get_text(separator="\n", strip=True)
    return data


class RichBourseMouvementsScraper(BaseScraper):
    """Fetch mouvement/analyse graphique page and extract data from div.panel."""

    def __init__(
        self,
        symbol: str,
        api_key: str | None = None,
        sleep_seconds: float | None = None,
    ):
        super().__init__(api_key=api_key, sleep_seconds=sleep_seconds)
        self._symbol = (symbol or "").strip().upper()

    @property
    def url(self) -> str:
        return f"{RICHBOURSE_MOUVEMENTS_BASE}/{self._symbol}"

    def scrape(self) -> dict[str, Any]:
        """Fetch page and extract all div.panel content."""
        out: dict[str, Any] = {
            "source": "richbourse_mouvements",
            "url": self.url,
            "symbol": self._symbol,
            "panels": [],
        }
        if not self._symbol:
            return out

        try:
            self._sleep()
            resp = requests.get(
                self.url,
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0"},
            )
            resp.raise_for_status()
            self._sleep()
            content = resp.text.replace("\xa0", "")
        except Exception as e:
            logger.warning("Fetch failed for %s: %s", self.url, e)
            out["error"] = str(e)
            return out

        soup = BeautifulSoup(content, "html.parser")

        # Find all div with class "panel" (or "panel panel-default", etc.)
        panels = soup.find_all("div", class_=re.compile(r"\bpanel\b"))
        for panel in panels:
            panel_data = _extract_panel_data(panel)
            if panel_data["title"] or panel_data["content"] or panel_data["tables"]:
                out["panels"].append(panel_data)

        # If no panels found by class, try data in main content
        if not out["panels"]:
            main = soup.find("div", class_=re.compile(r"content|main|mouvements"))
            if main:
                for div in main.find_all("div", recursive=False):
                    if div.get("class") and "panel" in " ".join(div.get("class", [])):
                        panel_data = _extract_panel_data(div)
                        if panel_data["title"] or panel_data["content"] or panel_data["tables"]:
                            out["panels"].append(panel_data)

        return out
