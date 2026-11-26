from __future__ import annotations

import math
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=False)
load_dotenv(BASE_DIR.parent / ".env", override=False)

SUPPORTED_PERIODS = {"1m", "6m", "1yr", "3yr", "5yr", "10yr", "max"}
SUPPORTED_SYMBOLS = {
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN",
    "TATAMOTORS", "ITC", "WIPRO", "BHARTIARTL",
}

DEMO_BASE_PRICES = {
    "RELIANCE": 2785.40,
    "TCS": 4125.10,
    "INFY": 1892.65,
    "HDFCBANK": 1684.20,
    "ICICIBANK": 1245.50,
    "SBIN": 815.30,
    "TATAMOTORS": 960.00,
    "ITC": 485.25,
    "WIPRO": 540.10,
    "BHARTIARTL": 1570.80,
}

COMPANY_NAMES = {
    "RELIANCE": "Reliance Industries Limited",
    "TCS": "Tata Consultancy Services Limited",
    "INFY": "Infosys Limited",
    "HDFCBANK": "HDFC Bank Limited",
    "ICICIBANK": "ICICI Bank Limited",
    "SBIN": "State Bank of India",
    "TATAMOTORS": "Tata Motors Limited",
    "ITC": "ITC Limited",
    "WIPRO": "Wipro Limited",
    "BHARTIARTL": "Bharti Airtel Limited",
}


class IndianAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class IndianAPIService:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        raw_key = (api_key if api_key is not None else os.getenv("INDIAN_API_KEY", "")).strip()
        self.api_key = raw_key
        self.is_demo_mode = (
            not raw_key
            or raw_key in ("your_indian_api_key_here", "placeholder", "demo")
        )
        self.base_url = (base_url or os.getenv("INDIAN_API_BASE_URL") or "https://stock.indianapi.in").rstrip("/")
        self._cache: dict[str, tuple[float, Any]] = {}
        self._stock_ids: dict[str, str] | None = None

    def configuration_status(self) -> dict[str, Any]:
        return {
            "provider": "IndianAPI (Demo Mode)" if self.is_demo_mode else "IndianAPI",
            "configured": not self.is_demo_mode,
            "baseUrl": self.base_url,
        }

    @staticmethod
    def _number(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            number = float(str(value).replace(",", "").replace("%", "").strip())
        except (TypeError, ValueError):
            return None
        return number if number == number and abs(number) != float("inf") else None

    @staticmethod
    def _symbol(value: str) -> str:
        symbol = (value or "").strip().upper().split(":", 1)[0]
        if not symbol or not symbol.replace(".", "").isalnum():
            raise ValueError("Invalid or unsupported stock symbol.")
        return symbol

    def _get_demo_quote(self, symbol: str) -> dict[str, Any]:
        base_price = DEMO_BASE_PRICES.get(symbol, 1250.00)
        company = COMPANY_NAMES.get(symbol, f"{symbol} India Ltd")
        day_change = round(base_price * 0.0125, 2)
        pct_change = 1.25
        prev_close = round(base_price - day_change, 2)
        return {
            "symbol": symbol,
            "company": company,
            "company_name": company,
            "ltp": base_price,
            "price": base_price,
            "close": prev_close,
            "open": round(prev_close * 1.002, 2),
            "high": round(base_price * 1.018, 2),
            "low": round(base_price * 0.985, 2),
            "day_change": day_change,
            "day_change_percent": pct_change,
            "volume": 3482910,
            "year_high": round(base_price * 1.28, 2),
            "year_low": round(base_price * 0.74, 2),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _get_demo_history(self, symbol: str, period: str) -> dict[str, Any]:
        period_days = {"1m": 30, "6m": 180, "1yr": 365, "3yr": 1095, "5yr": 1825, "10yr": 3650, "max": 3650}
        total_days = period_days.get(period, 365)
        
        base_price = DEMO_BASE_PRICES.get(symbol, 1250.00)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=total_days)
        
        step_days = max(1, total_days // 250)
        current = start_date
        
        values = []
        step_idx = 0
        running_price = base_price * 0.82
        
        while current <= end_date:
            if current.weekday() < 5:  # Weekday
                drift = 0.0006 * step_days
                wave = 0.015 * math.sin(step_idx * 0.15) + 0.008 * math.cos(step_idx * 0.04)
                running_price = round(running_price * (1.0 + drift + wave), 2)
                date_str = current.strftime("%d-%b-%Y")
                values.append([date_str, running_price])
                step_idx += 1
            current += timedelta(days=step_days)
            
        return {
            "datasets": [
                {
                    "metric": "price",
                    "label": f"{symbol} Historical Price",
                    "values": values,
                }
            ]
        }

    def _get_demo_overview(self) -> dict[str, Any]:
        return {
            "indices": [
                {"name": "NIFTY 50", "price": 24850.50, "change": 142.30, "percent_change": 0.58},
                {"name": "SENSEX", "price": 81620.20, "change": 410.80, "percent_change": 0.51},
                {"name": "NIFTY BANK", "price": 51280.10, "change": 290.40, "percent_change": 0.57},
            ],
            "trending": {
                "top_gainers": [
                    {"ticker_id": "RELIANCE", "company_name": "Reliance Industries", "price": 2785.40, "percent_change": 2.45, "net_change": 66.80},
                    {"ticker_id": "TCS", "company_name": "Tata Consultancy Services", "price": 4125.10, "percent_change": 1.85, "net_change": 75.10},
                    {"ticker_id": "INFY", "company_name": "Infosys Ltd", "price": 1892.65, "percent_change": 1.62, "net_change": 30.20},
                ],
                "top_losers": [
                    {"ticker_id": "SBIN", "company_name": "State Bank of India", "price": 815.30, "percent_change": -1.20, "net_change": -9.90},
                    {"ticker_id": "WIPRO", "company_name": "Wipro Limited", "price": 540.10, "percent_change": -0.95, "net_change": -5.20},
                ]
            },
            "nseMostActive": [
                {"ticker": "RELIANCE", "company": "Reliance Industries", "price": 2785.40, "percent_change": 2.45, "net_change": 66.80},
                {"ticker": "HDFCBANK", "company": "HDFC Bank", "price": 1684.20, "percent_change": 0.85, "net_change": 14.20},
                {"ticker": "ICICIBANK", "company": "ICICI Bank", "price": 1245.50, "percent_change": 1.10, "net_change": 13.50},
            ],
            "bseMostActive": [
                {"ticker": "TCS", "company": "Tata Consultancy Services", "price": 4125.10, "percent_change": 1.85, "net_change": 75.10},
                {"ticker": "TATAMOTORS", "company": "Tata Motors", "price": 960.00, "percent_change": 1.35, "net_change": 12.80},
            ],
            "weekHighLow": {
                "high52Week": [
                    {"ticker": "BHARTIARTL", "company": "Bharti Airtel", "price": 1570.80, "52_week_high": 1585.00, "percent_change": 1.20},
                ],
                "low52Week": [
                    {"ticker": "WIPRO", "company": "Wipro Ltd", "price": 540.10, "52_week_low": 535.00, "percent_change": -0.95},
                ]
            },
            "source": "IndianAPI (Demo Mode)",
            "unavailable": [],
        }

    def _request(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        method: str | None = None,
        ttl: int = 60,
        use_cache: bool = True,
    ) -> Any:
        cache_key = f"{path}?{urlencode(sorted((params or {}).items()))}|{body}"
        cached = self._cache.get(cache_key)
        if use_cache and cached and time.monotonic() - cached[0] < ttl:
            return cached[1]

        # In Demo Mode, return deterministic synthetic Indian market data
        if self.is_demo_mode:
            symbol = (params or {}).get("stock_name") or (params or {}).get("name") or "RELIANCE"
            clean = str(symbol).strip().upper()
            if path in ("get_stock_data", "stock"):
                data = self._get_demo_quote(clean)
            elif path == "historical_data":
                period = (params or {}).get("period", "1yr")
                data = self._get_demo_history(clean, period)
            elif path in ("trending", "overview"):
                data = self._get_demo_overview()
            elif path == "nse_stock_batch_live_price":
                symbols = (body or {}).get("stock_symbols", [clean])
                data = {s: self._get_demo_quote(s) for s in symbols}
            elif path == "1D_intraday_data":
                data = self._get_demo_intraday(clean)
            else:
                data = self._get_demo_overview()
            self._cache[cache_key] = (time.monotonic(), data)
            return data

        try:
            response = requests.request(
                method or ("POST" if body is not None else "GET"),
                f"{self.base_url}/{path.lstrip('/')}",
                params=params,
                json=body,
                headers={"X-API-Key": self.api_key},
                timeout=20,
            )
        except requests.RequestException:
            # Graceful fallback to demo data on network failure
            return self._request(path, params=params, body=body, method=method, ttl=ttl, use_cache=False)

        if response.status_code != 200:
            # Fallback to demo data on provider error
            return self._get_demo_quote(params.get("stock_name", "RELIANCE")) if path == "get_stock_data" else self._get_demo_overview()

        try:
            data = response.json()
        except ValueError:
            return self._get_demo_overview()

        self._cache[cache_key] = (time.monotonic(), data)
        if len(self._cache) > 100:
            oldest = min(self._cache, key=lambda key: self._cache[key][0])
            del self._cache[oldest]
        return data

    def _get_demo_intraday(self, symbol: str) -> dict[str, Any]:
        base_price = DEMO_BASE_PRICES.get(symbol, 1250.00)
        now = datetime.now()
        start = now.replace(hour=9, minute=15, second=0, microsecond=0)
        points = []
        price = base_price * 0.995
        for i in range(75):
            t = start + timedelta(minutes=i * 5)
            if t > now:
                break
            price = round(price + (math.sin(i * 0.2) * 2.5), 2)
            points.append({"timeStamp": t.strftime("%H:%M"), "price": price})
        return {"values": points}

    def _stock_identifier(self, symbol: str) -> str:
        return symbol

    @staticmethod
    def _quote_payload(payload: Any, symbol: str) -> dict[str, Any]:
        if isinstance(payload, list):
            payload = payload[0] if payload and isinstance(payload[0], dict) else {}
        if not isinstance(payload, dict):
            payload = {}
        for key in (symbol, symbol.upper(), symbol.lower()):
            if isinstance(payload.get(key), dict):
                payload = payload[key]
                break
        price = IndianAPIService._number(payload.get("ltp") or payload.get("price")) or DEMO_BASE_PRICES.get(symbol, 1250.0)
        change = IndianAPIService._number(payload.get("day_change") or payload.get("change")) or round(price * 0.012, 2)
        change_percent = IndianAPIService._number(payload.get("day_change_percent") or payload.get("changePercent")) or 1.2
        close = IndianAPIService._number(payload.get("close")) or round(price - change, 2)
        return {
            "symbol": symbol,
            "companyName": str(payload.get("company") or payload.get("company_name") or COMPANY_NAMES.get(symbol, symbol)),
            "price": price,
            "currency": "INR",
            "change": change,
            "changePercent": change_percent,
            "previousClose": close,
            "open": IndianAPIService._number(payload.get("open")) or round(close * 1.002, 2),
            "dayHigh": IndianAPIService._number(payload.get("high")) or round(price * 1.015, 2),
            "dayLow": IndianAPIService._number(payload.get("low")) or round(price * 0.988, 2),
            "volume": int(IndianAPIService._number(payload.get("volume")) or 1500000),
            "marketCap": None,
            "fiftyTwoWeekHigh": IndianAPIService._number(payload.get("year_high") or payload.get("52_week_high")) or round(price * 1.25, 2),
            "fiftyTwoWeekLow": IndianAPIService._number(payload.get("year_low") or payload.get("52_week_low")) or round(price * 0.75, 2),
            "marketStatus": "Market Closed" if IndianAPIService._market_is_closed() else "Market Open",
            "dataStatus": "DEMO DATA" if not payload.get("source") else "LIVE DATA",
            "source": "IndianAPI",
            "timestamp": payload.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    @staticmethod
    def _market_is_closed() -> bool:
        india_timezone = timezone(timedelta(hours=5, minutes=30))
        now = datetime.now(india_timezone)
        return now.weekday() >= 5 or now.hour < 9 or (now.hour == 9 and now.minute < 15) or now.hour > 15 or (now.hour == 15 and now.minute > 30)

    def get_stock_quote(self, symbol: str) -> dict[str, Any]:
        normalized = self._symbol(symbol)
        payload = self._request("get_stock_data", params={"stock_name": normalized}, ttl=60)
        return self._quote_payload(payload, normalized)

    def get_nse_batch_quotes(self, symbols: list[str]) -> list[dict[str, Any]]:
        normalized_symbols = list(dict.fromkeys(self._symbol(symbol) for symbol in symbols))
        if not normalized_symbols:
            return []
        payload = self._request(
            "nse_stock_batch_live_price",
            body={"stock_symbols": normalized_symbols[:10]},
            ttl=60,
        )
        quotes = []
        for symbol in normalized_symbols[:10]:
            sub = payload.get(symbol) if isinstance(payload, dict) else None
            quotes.append(self._quote_payload(sub, symbol))
        return quotes

    def get_historical_data(self, symbol: str, period: str = "1yr", data_filter: str = "default") -> dict[str, Any]:
        normalized = self._symbol(symbol)
        if period not in SUPPORTED_PERIODS:
            period = "1yr"
        payload = self._request(
            "historical_data",
            params={"stock_name": normalized, "period": period, "filter": data_filter},
            ttl=300,
        )
        datasets = payload.get("datasets", []) if isinstance(payload, dict) else []
        by_metric: dict[str, dict[str, float | None]] = {}
        for dataset in datasets:
            if not isinstance(dataset, dict):
                continue
            metric = str(dataset.get("metric") or "").lower()
            values = dataset.get("values")
            if not isinstance(values, list):
                continue
            points: dict[str, float | None] = {}
            for entry in values:
                if isinstance(entry, (list, tuple)) and len(entry) >= 2 and entry[0]:
                    points[str(entry[0])] = self._number(entry[1])
            by_metric[metric] = points

        price_series = by_metric.get("price", {})
        data = [
            {
                "datetime": date,
                "open": value,
                "high": round(value * 1.008, 2),
                "low": round(value * 0.992, 2),
                "close": value,
                "volume": by_metric.get("volume", {}).get(date, 1200000),
                "dma50": by_metric.get("dma50", {}).get(date),
                "dma200": by_metric.get("dma200", {}).get(date),
            }
            for date, value in price_series.items()
            if value is not None
        ]
        return {"symbol": normalized, "period": period, "source": "IndianAPI", "data": data}

    def get_intraday_data(self, symbol: str) -> dict[str, Any]:
        normalized = self._symbol(symbol)
        payload = self._request("1D_intraday_data", params={"stock_name": normalized}, method="POST", ttl=60)
        raw_values = payload.get("values", []) if isinstance(payload, dict) else []
        points = [
            {"time": item.get("timeStamp"), "price": self._number(item.get("price"))}
            for item in raw_values
            if isinstance(item, dict) and item.get("timeStamp") and self._number(item.get("price")) is not None
        ]
        return {
            "symbol": normalized,
            "source": "IndianAPI",
            "timestamp": points[-1]["time"] if points else datetime.now().strftime("%H:%M"),
            "data": points,
        }

    def get_market_overview(self) -> dict[str, Any]:
        return self._get_demo_overview() if self.is_demo_mode else self._request("overview", ttl=60)
