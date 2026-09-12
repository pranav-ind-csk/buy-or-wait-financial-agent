"""
Deterministic currency conversion utilities using Decimal and exchange_rates.csv.
"""
import csv
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Tuple, Optional
import os

class CurrencyConverter:
    def __init__(self, exchange_rates_path: str = "dataset/exchange_rates.csv"):
        # Map (date, from_currency, to_currency) -> Decimal(rate)
        self.direct_rates: Dict[Tuple[str, str, str], Decimal] = {}
        # Also store by (month_str, from_curr, to_curr)
        self.monthly_rates: Dict[Tuple[str, str, str], Decimal] = {}
        self._load_rates(exchange_rates_path)

    def _load_rates(self, path: str):
        if not os.path.exists(path):
            return
        with open(path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                dt = row["rate_date"].strip()
                fc = row["from_currency"].strip().upper()
                tc = row["to_currency"].strip().upper()
                rate = Decimal(row["rate"].strip())
                self.direct_rates[(dt, fc, tc)] = rate
                month = dt[:7]
                self.monthly_rates[(month, fc, tc)] = rate

    def get_rate(self, from_curr: str, to_curr: str, date: str) -> Optional[Decimal]:
        fc = from_curr.strip().upper()
        tc = to_curr.strip().upper()
        if fc == tc:
            return Decimal("1")

        # 1. Exact date
        if (date, fc, tc) in self.direct_rates:
            return self.direct_rates[(date, fc, tc)]
        if (date, tc, fc) in self.direct_rates:
            return Decimal("1") / self.direct_rates[(date, tc, fc)]

        # 2. Same month (YYYY-MM-15)
        month = date[:7]
        if (month, fc, tc) in self.monthly_rates:
            return self.monthly_rates[(month, fc, tc)]
        if (month, tc, fc) in self.monthly_rates:
            return Decimal("1") / self.monthly_rates[(month, tc, fc)]

        # 3. Intermediate currency via USD or EUR
        for inter in ["USD", "EUR"]:
            r1 = self.get_rate(fc, inter, date)
            r2 = self.get_rate(inter, tc, date)
            if r1 is not None and r2 is not None:
                return r1 * r2

        # 4. Fallback to closest available date
        available_dates = sorted(set(d for (d, f, t) in self.direct_rates if (f == fc and t == tc) or (f == tc and t == fc)))
        if available_dates:
            closest_date = min(available_dates, key=lambda d: abs((int(d.replace("-", "")) - int(date.replace("-", "")))))
            if (closest_date, fc, tc) in self.direct_rates:
                return self.direct_rates[(closest_date, fc, tc)]
            if (closest_date, tc, fc) in self.direct_rates:
                return Decimal("1") / self.direct_rates[(closest_date, tc, fc)]

        return None

    def convert(self, amount: Decimal, from_curr: str, to_curr: str, date: str) -> Decimal:
        if from_curr.strip().upper() == to_curr.strip().upper():
            return amount
        rate = self.get_rate(from_curr, to_curr, date)
        if rate is None:
            raise ValueError(f"No exchange rate found for {from_curr} -> {to_curr} on {date}")
        converted = amount * rate
        return converted
