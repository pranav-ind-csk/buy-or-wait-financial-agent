"""
Data loader and indexing layer.
Loads all dataset CSV files and integrates multimodal image evidence.
"""
import csv
import os
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from code.models import FinancialProfile, FinancialEvent, PaymentOption, EvaluationRequest
from code.evidence_extractor import EvidenceExtractor

class DataLoader:
    def __init__(self, dataset_dir: str = "dataset"):
        self.dataset_dir = dataset_dir
        self.evidence_extractor = EvidenceExtractor()
        
        self.profiles: Dict[str, FinancialProfile] = {}
        self.events_by_user: Dict[str, List[FinancialEvent]] = {}
        self.payment_options_by_request: Dict[str, List[PaymentOption]] = {}
        self.messages_by_user: Dict[str, List[Dict[str, str]]] = {}
        self.requests: List[EvaluationRequest] = []
        self.sample_requests: List[Dict[str, Any]] = []
        
        self.image_event_map: Dict[str, str] = {}  # event_id -> image_id

    def load_all(self):
        self._load_images_map()
        self._load_profiles()
        self._load_events()
        self._load_payment_options()
        self._load_messages()
        self._load_requests()

    def _load_images_map(self):
        path = os.path.join(self.dataset_dir, "images.csv")
        if not os.path.exists(path):
            return
        with open(path, mode="r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                img_id = row["image_id"].strip()
                evt_id = row["related_event_id"].strip()
                if evt_id:
                    self.image_event_map[evt_id] = img_id

    def _load_profiles(self):
        path = os.path.join(self.dataset_dir, "financial_profiles.csv")
        if not os.path.exists(path):
            return
        with open(path, mode="r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                uid = row["user_id"].strip()
                curr = row["home_currency"].strip()
                bal = Decimal(row["current_available_balance"].strip())
                min_bal = Decimal(row["minimum_balance_to_keep"].strip())
                priorities = [p.strip() for p in row["financial_priorities"].split("|") if p.strip()]
                protect = [p.strip() for p in row["expense_categories_to_protect"].split("|") if p.strip()]
                reduce_cats = [p.strip() for p in row["expense_categories_user_is_willing_to_reduce"].split("|") if p.strip()]
                stop_cats = [p.strip() for p in row["expense_categories_user_is_willing_to_stop"].split("|") if p.strip()]
                methods = [p.strip() for p in row["payment_methods_user_will_consider"].split("|") if p.strip()]
                max_inst = int(row["max_installment_months"].strip()) if row["max_installment_months"].strip() else None

                self.profiles[uid] = FinancialProfile(
                    user_id=uid,
                    home_currency=curr,
                    current_available_balance=bal,
                    minimum_balance_to_keep=min_bal,
                    financial_priorities=priorities,
                    expense_categories_to_protect=protect,
                    expense_categories_user_is_willing_to_reduce=reduce_cats,
                    expense_categories_user_is_willing_to_stop=stop_cats,
                    payment_methods_user_will_consider=methods,
                    max_installment_months=max_inst
                )

    def _load_events(self):
        path = os.path.join(self.dataset_dir, "financial_events.csv")
        if not os.path.exists(path):
            return
        with open(path, mode="r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                evt_id = row["event_id"].strip()
                uid = row["user_id"].strip()
                evt_type = row["event_type"].strip()
                desc = row["description"].strip()
                cat = row["category"].strip()
                direction = row["direction"].strip()
                amt_str = row["amount"].strip()
                currency = row["currency"].strip()
                event_date = row["event_date"].strip()
                settlement_date = row["settlement_date"].strip()
                status = row["status"].strip()
                linked_id = row["linked_event_id"].strip()
                flex = row["flexibility"].strip() or "fixed"
                min_amt = Decimal(row["minimum_allowed_amount"].strip()) if row["minimum_allowed_amount"].strip() else None

                # Multimodal resolution for missing amount
                if not amt_str:
                    img_id = self.image_event_map.get(evt_id)
                    if img_id:
                        img_fact = self.evidence_extractor.extract_from_image(img_id)
                        if img_fact:
                            amt = img_fact["amount"]
                            if not currency:
                                currency = img_fact["currency"]
                        else:
                            amt = Decimal("0")
                    else:
                        amt = Decimal("0")
                else:
                    amt = Decimal(amt_str)

                event = FinancialEvent(
                    event_id=evt_id,
                    user_id=uid,
                    event_type=evt_type,
                    description=desc,
                    category=cat,
                    direction=direction,
                    amount=amt,
                    currency=currency,
                    event_date=event_date,
                    settlement_date=settlement_date,
                    status=status,
                    linked_event_id=linked_id,
                    flexibility=flex,
                    minimum_allowed_amount=min_amt
                )
                if uid not in self.events_by_user:
                    self.events_by_user[uid] = []
                self.events_by_user[uid].append(event)

    def _load_payment_options(self):
        path = os.path.join(self.dataset_dir, "request_payment_options.csv")
        if not os.path.exists(path):
            return
        with open(path, mode="r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                opt_id = row["payment_option_id"].strip()
                req_id = row["request_id"].strip()
                method = row["payment_method"].strip()
                amt = Decimal(row["payment_amount"].strip())
                num_pay = int(row["number_of_payments"].strip())
                first_date = row["first_payment_date"].strip()
                freq = int(row["payment_frequency_days"].strip()) if row["payment_frequency_days"].strip() else None
                fee = Decimal(row["financing_fee"].strip())
                total = Decimal(row["total_payable_amount"].strip())

                option = PaymentOption(
                    payment_option_id=opt_id,
                    request_id=req_id,
                    payment_method=method,
                    payment_amount=amt,
                    number_of_payments=num_pay,
                    first_payment_date=first_date,
                    payment_frequency_days=freq,
                    financing_fee=fee,
                    total_payable_amount=total
                )
                if req_id not in self.payment_options_by_request:
                    self.payment_options_by_request[req_id] = []
                self.payment_options_by_request[req_id].append(option)

    def _load_messages(self):
        path = os.path.join(self.dataset_dir, "messages.csv")
        if not os.path.exists(path):
            return
        with open(path, mode="r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                uid = row["user_id"].strip()
                if uid not in self.messages_by_user:
                    self.messages_by_user[uid] = []
                self.messages_by_user[uid].append(row)

    def _load_requests(self):
        path = os.path.join(self.dataset_dir, "requests.csv")
        if not os.path.exists(path):
            return
        with open(path, mode="r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                self.requests.append(EvaluationRequest(
                    request_id=row["request_id"].strip(),
                    user_id=row["user_id"].strip(),
                    request_date=row["request_date"].strip(),
                    request_type=row["request_type"].strip(),
                    requested_amount=Decimal(row["requested_amount"].strip()),
                    desired_completion_date=row["desired_completion_date"].strip(),
                    allows_partial_payment=row["allows_partial_payment"].strip().lower() == "true",
                    request_text=row["request_text"].strip()
                ))

    def load_sample_requests(self) -> List[Dict[str, Any]]:
        path = os.path.join(self.dataset_dir, "sample_requests.csv")
        if not os.path.exists(path):
            return []
        with open(path, mode="r", encoding="utf-8") as f:
            return list(csv.DictReader(f))
