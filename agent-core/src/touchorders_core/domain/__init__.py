"""Pure domain vocabulary. This package has no internal dependencies."""

from touchorders_core.domain.events import DomainEvent, OperationalEvent
from touchorders_core.domain.incidents import IncidentReport, IncidentReportOutput
from touchorders_core.domain.plans import ActionPlan, ActionPlanOutput
from touchorders_core.domain.reports import BusinessReport, BusinessReportOutput, KPISnapshot

__all__ = [
    "ActionPlan", "ActionPlanOutput", "BusinessReport", "BusinessReportOutput",
    "DomainEvent", "IncidentReport", "IncidentReportOutput", "KPISnapshot",
    "OperationalEvent",
]
