"""
Domain models for the Buy or Wait? personal financial decision agent.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional, Dict, Any

@dataclass
class FinancialProfile:
    user_id: str
    home_currency: str
    current_available_balance: Decimal
    minimum_balance_to_keep: Decimal
    financial_priorities: List[str] = field(default_factory=list)
    expense_categories_to_protect: List[str] = field(default_factory=list)
    expense_categories_user_is_willing_to_reduce: List[str] = field(default_factory=list)
    expense_categories_user_is_willing_to_stop: List[str] = field(default_factory=list)
    payment_methods_user_will_consider: List[str] = field(default_factory=list)
    max_installment_months: Optional[int] = None

@dataclass
class FinancialEvent:
    event_id: str
    user_id: str
    event_type: str
    description: str
    category: str
    direction: str  # credit or debit
    amount: Decimal
    currency: str
    event_date: str
    settlement_date: str
    status: str  # settled, pending, scheduled, cancelled, failed, unrealized
    linked_event_id: str = ""
    flexibility: str = "fixed"  # fixed, stoppable, reducible, reducible_or_stoppable
    minimum_allowed_amount: Optional[Decimal] = None

@dataclass
class PaymentOption:
    payment_option_id: str
    request_id: str
    payment_method: str  # full_payment, installments
    payment_amount: Decimal
    number_of_payments: int
    first_payment_date: str
    payment_frequency_days: Optional[int]
    financing_fee: Decimal
    total_payable_amount: Decimal

@dataclass
class EvaluationRequest:
    request_id: str
    user_id: str
    request_date: str
    request_type: str
    requested_amount: Decimal
    desired_completion_date: str
    allows_partial_payment: bool
    request_text: str

@dataclass
class SpendingChange:
    action: str  # "stop" or "reduce_to"
    event_id: str
    new_amount: Optional[Decimal] = None
    description: str = ""
    category: str = ""

    def to_output_str(self) -> str:
        if self.action == "stop":
            return f"stop:{self.event_id}"
        elif self.action == "reduce_to":
            assert self.new_amount is not None
            # format cleanly without unnecessary trailing zeros or scientific notation
            val_str = f"{self.new_amount:f}".rstrip('0').rstrip('.') if '.' in f"{self.new_amount:f}" else f"{self.new_amount}"
            return f"reduce_to:{self.event_id}:{val_str}"
        return "none"

@dataclass
class PaymentScheduleItem:
    date: str
    amount: Decimal

@dataclass
class CandidatePlan:
    payment_method: str  # full_payment, partial_payment, installments, wait, not_recommended
    affordability_status: str  # affordable_now, affordable_with_plan, affordable_later, not_affordable
    schedule: List[PaymentScheduleItem] = field(default_factory=list)
    spending_changes: List[SpendingChange] = field(default_factory=list)
    earliest_date_for_full_payment: str = ""
    payment_option_id: Optional[str] = None
    total_amount_paid: Decimal = Decimal('0')
    number_of_payments: int = 0
    first_payment_date: str = ""
    completion_date: str = ""
    is_safe: bool = False
    min_balance_reached: Decimal = Decimal('0')
    min_balance_date: str = ""

    def payment_plan_str(self) -> str:
        if not self.schedule or self.payment_method == "not_recommended":
            return "none"
        items = []
        for item in self.schedule:
            val_str = f"{item.amount:f}".rstrip('0').rstrip('.') if '.' in f"{item.amount:f}" else f"{item.amount}"
            items.append(f"{item.date}:{val_str}")
        return "|".join(items)

    def spending_changes_str(self) -> str:
        if not self.spending_changes:
            return "none"
        return "|".join(c.to_output_str() for c in self.spending_changes[:3])

@dataclass
class DecisionResult:
    request_id: str
    amount_safe_to_pay: Decimal
    affordability_status: str
    recommended_payment_method: str
    payment_plan: str
    earliest_date_for_full_payment: str
    spending_changes_needed: str
    decision_explanation: str
