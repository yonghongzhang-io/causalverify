"""
yFinance Connector
==================
Downloads equity price data, computes returns, and supports
event-study and panel-data preparation.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from typing import Union


class YFinanceConnector:

    def get_prices(
        self,
        tickers: Union[str, list],
        start: str,
        end: str,
        field: str = "Close",
    ) -> pd.DataFrame:
        """
        Download daily price data for one or more tickers.

        Parameters
        ----------
        tickers : str or list
        start   : "YYYY-MM-DD"
        end     : "YYYY-MM-DD"
        field   : "Close" | "Open" | "High" | "Low" | "Volume"

        Returns
        -------
        pd.DataFrame  columns = tickers, index = DatetimeIndex
        """
        if isinstance(tickers, str):
            tickers = [tickers]

        raw = yf.download(tickers, start=start, end=end, progress=False, auto_adjust=True)

        if isinstance(raw.columns, pd.MultiIndex):
            if field in raw.columns.get_level_values(0):
                prices = raw[field].copy()
            else:
                prices = raw["Close"].copy()
        else:
            prices = raw[[field]].copy() if field in raw.columns else raw[["Close"]].copy()
            prices.columns = tickers

        prices.index = pd.to_datetime(prices.index)
        return prices.dropna(how="all")

    def get_returns(
        self,
        tickers: Union[str, list],
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Daily simple returns."""
        prices = self.get_prices(tickers, start=start, end=end)
        return prices.pct_change().dropna()

    def get_abnormal_returns(
        self,
        tickers: Union[str, list],
        benchmark: str,
        data_start: str,
        data_end: str,
        est_start: str,
        est_end: str,
    ) -> pd.DataFrame:
        """
        Market-model abnormal returns.
        AR_it = R_it − (α_i + β_i · R_mkt_t)
        Estimation window: [est_start, est_end]
        """
        if isinstance(tickers, str):
            tickers = [tickers]
        all_tickers = list(dict.fromkeys(tickers + [benchmark]))

        ret = self.get_returns(all_tickers, start=data_start, end=data_end)
        est = ret.loc[est_start:est_end]

        ar = pd.DataFrame(index=ret.index)
        betas = {}
        for t in tickers:
            if t not in ret.columns or benchmark not in ret.columns:
                continue
            valid = est[[benchmark, t]].dropna()
            b, a = np.polyfit(valid[benchmark], valid[t], 1)
            betas[t] = {"alpha": a, "beta": b}
            ar[t] = ret[t] - (a + b * ret[benchmark])

        ar.attrs["betas"] = betas
        return ar.dropna(how="all")

    def build_event_panel(
        self,
        tickers: Union[str, list],
        benchmark: str,
        event_date: str,
        window: tuple = (-10, 10),
        est_start: str = None,
        est_end: str = None,
    ) -> pd.DataFrame:
        """
        Build a panel of abnormal returns around an event date.

        Returns DataFrame with columns: ticker, t (relative day), date, ar, car
        """
        if isinstance(tickers, str):
            tickers = [tickers]

        event_dt = pd.Timestamp(event_date)
        data_start = (event_dt + pd.tseries.offsets.BDay(window[0] - 30)).strftime("%Y-%m-%d")
        data_end   = (event_dt + pd.tseries.offsets.BDay(window[1] + 30)).strftime("%Y-%m-%d")

        if est_start is None:
            est_start = (event_dt - pd.tseries.offsets.BDay(250)).strftime("%Y-%m-%d")
        if est_end is None:
            est_end = (event_dt - pd.tseries.offsets.BDay(30)).strftime("%Y-%m-%d")

        ar = self.get_abnormal_returns(
            tickers, benchmark,
            data_start=data_start, data_end=data_end,
            est_start=est_start, est_end=est_end,
        )

        # Find event day index
        trading_days = ar.index
        event_idx = trading_days.get_indexer([event_dt], method="nearest")[0]

        rows = []
        for t_offset in range(window[0], window[1] + 1):
            idx = event_idx + t_offset
            if idx < 0 or idx >= len(trading_days):
                continue
            date = trading_days[idx]
            for ticker in tickers:
                if ticker not in ar.columns:
                    continue
                rows.append({
                    "ticker": ticker,
                    "t": t_offset,
                    "date": date,
                    "ar": ar.loc[date, ticker],
                })

        panel = pd.DataFrame(rows)
        if not panel.empty:
            panel["car"] = panel.groupby("ticker")["ar"].cumsum()
        return panel
