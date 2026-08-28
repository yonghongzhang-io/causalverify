"""
FRED Connector
==============
Fetches time series from the Federal Reserve Economic Data API.
Requires FRED_API_KEY in .env.

Common series used in this project:
  BUSLOANS  — Commercial & Industrial Loans, All Commercial Banks
  TOTLL     — Total Loans and Leases, All Commercial Banks
  FEDFUNDS  — Federal Funds Rate
  DGS10     — 10-Year Treasury Constant Maturity Rate
  DPCREDIT  — Discount Window Primary Credit Rate
  VIXCLS    — CBOE Volatility Index (VIX)
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class FREDConnector:
    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
    RATE_LIMIT_PAUSE = 0.5  # seconds between requests

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("FRED_API_KEY")
        if not self.api_key:
            raise ValueError(
                "FRED_API_KEY not found. Set it in .env or pass api_key=... "
                "Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html"
            )
        self._last_request = 0.0

    def _throttle(self):
        elapsed = time.time() - self._last_request
        if elapsed < self.RATE_LIMIT_PAUSE:
            time.sleep(self.RATE_LIMIT_PAUSE - elapsed)
        self._last_request = time.time()

    def get_series(
        self,
        series_id: str,
        start: str = None,
        end: str = None,
        frequency: str = None,
    ) -> pd.Series:
        """
        Fetch a FRED series as a pandas Series with DatetimeIndex.

        Parameters
        ----------
        series_id : str   e.g. "BUSLOANS"
        start     : str   "YYYY-MM-DD"  (optional)
        end       : str   "YYYY-MM-DD"  (optional)
        frequency : str   "d","w","m","q","a" — aggregation frequency (optional)

        Returns
        -------
        pd.Series  with DatetimeIndex, name = series_id
        """
        self._throttle()
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
        }
        if start:
            params["observation_start"] = start
        if end:
            params["observation_end"] = end
        if frequency:
            params["frequency"] = frequency

        try:
            resp = requests.get(self.BASE_URL, params=params, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise ConnectionError(f"FRED API request failed for {series_id}: {e}") from e

        data = resp.json()
        if "observations" not in data:
            raise ValueError(f"No observations returned for {series_id}: {data}")

        records = [
            (obs["date"], obs["value"])
            for obs in data["observations"]
            if obs["value"] != "."
        ]
        if not records:
            return pd.Series(name=series_id, dtype=float)

        dates, values = zip(*records)
        series = pd.Series(
            pd.to_numeric(values, errors="coerce"),
            index=pd.to_datetime(dates),
            name=series_id,
        ).dropna()
        return series

    def get_multiple(
        self,
        series_ids: list,
        start: str = None,
        end: str = None,
        frequency: str = None,
    ) -> pd.DataFrame:
        """Fetch multiple series and return as aligned DataFrame."""
        frames = {}
        for sid in series_ids:
            try:
                frames[sid] = self.get_series(sid, start=start, end=end, frequency=frequency)
            except Exception as e:
                print(f"  [WARN] Could not fetch {sid}: {e}")
        if not frames:
            return pd.DataFrame()
        return pd.DataFrame(frames)

    # ── Common series shortcuts ──────────────────────────────────────

    def commercial_industrial_loans(self, start=None, end=None) -> pd.Series:
        """BUSLOANS — weekly commercial & industrial loans (billions USD)."""
        return self.get_series("BUSLOANS", start=start, end=end)

    def total_bank_loans(self, start=None, end=None) -> pd.Series:
        """TOTLL — total loans and leases at commercial banks."""
        return self.get_series("TOTLL", start=start, end=end)

    def fed_funds_rate(self, start=None, end=None) -> pd.Series:
        """FEDFUNDS — effective federal funds rate (monthly)."""
        return self.get_series("FEDFUNDS", start=start, end=end)

    def treasury_10y(self, start=None, end=None) -> pd.Series:
        """DGS10 — 10-year Treasury constant maturity rate (daily)."""
        return self.get_series("DGS10", start=start, end=end)

    def vix(self, start=None, end=None) -> pd.Series:
        """VIXCLS — CBOE Volatility Index (daily)."""
        return self.get_series("VIXCLS", start=start, end=end)
