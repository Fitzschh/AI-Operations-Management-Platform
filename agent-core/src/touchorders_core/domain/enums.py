"""Closed domain vocabularies and deterministic ordering helpers."""

from __future__ import annotations

from enum import StrEnum


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        return {self.INFO: 0, self.WARNING: 1, self.HIGH: 2, self.CRITICAL: 3}[self]

    @classmethod
    def at_least(cls, left: "Severity", right: "Severity") -> bool:
        return left.rank >= right.rank


class RiskTier(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    @property
    def rank(self) -> int:
        return {self.LOW: 0, self.MEDIUM: 1, self.HIGH: 2}[self]


class Priority(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class SideEffects(StrEnum):
    READ = "READ"
    WRITE = "WRITE"
    EXTERNAL = "EXTERNAL"


class IncidentCategory(StrEnum):
    INVENTORY_RISK = "INVENTORY_RISK"
    DEMAND_SPIKE = "DEMAND_SPIKE"
    KITCHEN_OVERLOAD = "KITCHEN_OVERLOAD"
    SALES_ANOMALY = "SALES_ANOMALY"
    CANCELLATION_SPIKE = "CANCELLATION_SPIKE"
    COMPOSITE = "COMPOSITE"


class Confidence(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Horizon(StrEnum):
    TODAY = "TODAY"
    THIS_WEEK = "THIS_WEEK"
    THIS_MONTH = "THIS_MONTH"


class AgentName(StrEnum):
    REALTIME_ANALYST = "realtime_analyst"
    BUSINESS_ANALYST = "business_analyst"
    OPERATIONS_MANAGER = "operations_manager"


class OperationalEventStatus(StrEnum):
    RECEIVED = "RECEIVED"
    SUPPRESSED = "SUPPRESSED"
    QUEUED = "QUEUED"
    DISPATCHED = "DISPATCHED"
    CONSUMED = "CONSUMED"
    DEAD_LETTER = "DEAD_LETTER"


class IncidentState(StrEnum):
    OPEN = "OPEN"
    PLANNING = "PLANNING"
    PLANNED = "PLANNED"
    DEFERRED = "DEFERRED"
    RESOLVED = "RESOLVED"
    MANUAL_HANDLING_REQUIRED = "MANUAL_HANDLING_REQUIRED"


class PlanState(StrEnum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    AUTO_APPROVED = "AUTO_APPROVED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    FAILED_VALIDATION = "FAILED_VALIDATION"


class ApprovalState(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"
    EXPIRED = "EXPIRED"


class WorkflowState(StrEnum):
    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    COMPENSATING = "COMPENSATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    COMPENSATED = "COMPENSATED"
    REQUIRES_MANUAL_CLEANUP = "REQUIRES_MANUAL_CLEANUP"


class WorkflowStepState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    STALE = "STALE"
    SKIPPED_DUPLICATE = "SKIPPED_DUPLICATE"
    COMPENSATED = "COMPENSATED"
    COMPENSATION_FAILED = "COMPENSATION_FAILED"


class MessageType(StrEnum):
    INCIDENT_REPORT_READY = "IncidentReportReady"
    BUSINESS_REPORT_RELEVANT = "BusinessReportRelevant"
    APPROVAL_DECIDED = "ApprovalDecided"
    WORKFLOW_COMPLETED = "WorkflowCompleted"
    WORKFLOW_FAILED = "WorkflowFailed"
    PLAN_EXPIRED = "PlanExpired"
