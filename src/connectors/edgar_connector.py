"""
SEC EDGAR Connector
===================
Fetches company filings from the SEC EDGAR full-text search API.
No API key required — uses the public EDGAR endpoints.

Rate limit: max 10 requests/second (EDGAR policy).
User-agent header is required by SEC.
"""

import time
import requests
import pandas as pd
from typing import Optional

# SEC requires a descriptive User-Agent: "Name email"
DEFAULT_USER_AGENT = "FinancialScientist research@example.com"


class EDGARConnector:
    SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
    COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
    RATE_LIMIT_PAUSE = 0.15  # 10 req/s max

    def __init__(self, user_agent: str = DEFAULT_USER_AGENT):
        self.headers = {"User-Agent": user_agent}
        self._last_request = 0.0

    def _throttle(self):
        elapsed = time.time() - self._last_request
        if elapsed < self.RATE_LIMIT_PAUSE:
            time.sleep(self.RATE_LIMIT_PAUSE - elapsed)
        self._last_request = time.time()

    def _get(self, url: str, params: dict = None) -> dict:
        self._throttle()
        resp = requests.get(url, headers=self.headers, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    # ── Company lookup ───────────────────────────────────────────────

    def get_cik(self, company_name: str) -> Optional[str]:
        """
        Search for a company's CIK number by name.
        Returns the first match's CIK (zero-padded to 10 digits).
        """
        url = "https://efts.sec.gov/LATEST/search-index"
        params = {"q": f'"{company_name}"', "dateRange": "custom",
                  "category": "form-type", "forms": "10-K"}
        try:
            data = self._get(
                "https://efts.sec.gov/LATEST/search-index",
                params={"q": company_name, "forms": "10-K", "hits.hits._source": "period_of_report"}
            )
            hits = data.get("hits", {}).get("hits", [])
            if hits:
                return hits[0]["_source"].get("entity_id", "").zfill(10)
        except Exception:
            pass
        return None

    def get_submissions(self, cik: str) -> dict:
        """
        Fetch all filings metadata for a company by CIK.
        CIK should be zero-padded to 10 digits.
        """
        cik = str(cik).zfill(10)
        return self._get(self.SUBMISSIONS_URL.format(cik=cik))

    def get_filings(
        self,
        cik: str,
        filing_type: str = "8-K",
        start: str = None,
        end: str = None,
        max_results: int = 100,
    ) -> pd.DataFrame:
        """
        Return a DataFrame of filings for a company.

        Parameters
        ----------
        cik          : str   10-digit CIK (zero-padded)
        filing_type  : str   e.g. "8-K", "10-K", "10-Q", "DEF 14A"
        start        : str   "YYYY-MM-DD"
        end          : str   "YYYY-MM-DD"
        max_results  : int

        Returns
        -------
        pd.DataFrame  with columns: accessionNumber, filingDate, form, primaryDocument
        """
        cik = str(cik).zfill(10)
        data = self.get_submissions(cik)

        recent = data.get("filings", {}).get("recent", {})
        if not recent:
            return pd.DataFrame()

        df = pd.DataFrame({
            "accessionNumber": recent.get("accessionNumber", []),
            "filingDate":      recent.get("filingDate", []),
            "form":            recent.get("form", []),
            "primaryDocument": recent.get("primaryDocument", []),
            "reportDate":      recent.get("reportDate", []),
        })

        df["filingDate"] = pd.to_datetime(df["filingDate"])
        df = df[df["form"] == filing_type]

        if start:
            df = df[df["filingDate"] >= pd.Timestamp(start)]
        if end:
            df = df[df["filingDate"] <= pd.Timestamp(end)]

        return df.head(max_results).reset_index(drop=True)

    def get_company_facts(self, cik: str, concept: str = "us-gaap",
                          tag: str = "Loans") -> pd.DataFrame:
        """
        Fetch XBRL financial facts for a company.
        Useful for getting reported loan volumes, assets, etc.

        Example:
            connector.get_company_facts("0000040729", tag="LoansAndLeasesReceivableNetReportedAmount")
        """
        cik = str(cik).zfill(10)
        data = self._get(self.COMPANY_FACTS_URL.format(cik=cik))

        facts = data.get("facts", {}).get(concept, {}).get(tag, {})
        if not facts:
            return pd.DataFrame()

        units = facts.get("units", {})
        rows = []
        for unit, obs_list in units.items():
            for obs in obs_list:
                rows.append({
                    "end": obs.get("end"),
                    "val": obs.get("val"),
                    "unit": unit,
                    "form": obs.get("form"),
                    "frame": obs.get("frame"),
                })
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df["end"] = pd.to_datetime(df["end"])
        return df.sort_values("end").reset_index(drop=True)

    def search_filings(
        self,
        query: str,
        forms: str = "8-K",
        start: str = None,
        end: str = None,
        max_results: int = 20,
    ) -> pd.DataFrame:
        """
        Full-text search across EDGAR filings.

        Parameters
        ----------
        query   : str   keyword or phrase, e.g. "Basel III capital requirements"
        forms   : str   comma-separated form types, e.g. "8-K,10-K"
        """
        params = {
            "q": query,
            "forms": forms,
            "hits.hits.total.value": max_results,
        }
        if start:
            params["dateRange"] = "custom"
            params["startdt"] = start
        if end:
            params["enddt"] = end

        try:
            data = self._get(
                "https://efts.sec.gov/LATEST/search-index",
                params=params,
            )
        except Exception as e:
            print(f"  [WARN] EDGAR search failed: {e}")
            return pd.DataFrame()

        hits = data.get("hits", {}).get("hits", [])
        rows = []
        for h in hits[:max_results]:
            src = h.get("_source", {})
            rows.append({
                "entity_name":    src.get("display_names", [{}])[0].get("name", ""),
                "form":           src.get("form_type", ""),
                "filed":          src.get("file_date", ""),
                "period":         src.get("period_of_report", ""),
                "accession":      src.get("file_num", ""),
                "description":    src.get("form_type", ""),
            })
        return pd.DataFrame(rows)
