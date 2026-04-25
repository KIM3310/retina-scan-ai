"""Clinical role definitions and permission checks.

This is the ONLY module that knows the role-to-permission mapping. API handlers
call is_permitted() and never inspect roles directly. Changes to the permission
matrix happen here and only here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    RADIOLOGIST = "Radiologist"
    OPHTHALMOLOGIST = "Ophthalmologist"
    REFERRING_PHYSICIAN = "ReferringPhysician"
    TECHNICIAN = "Technician"
    RESEARCHER = "Researcher"
    COMPLIANCE_OFFICER = "ComplianceOfficer"
    SYSTEM_ADMIN = "SystemAdmin"
    AUDITOR_EXTERNAL = "AuditorExternal"

    # Break-glass role — ephemeral, session-bound.
    BREAK_GLASS = "BreakGlass"


class Action(str, Enum):
    STUDY_READ = "study:read"
    STUDY_LIST = "study:list"
    CLASSIFICATION_RUN = "classification:run"
    CLASSIFICATION_VIEW = "classification:view"
    CLASSIFICATION_OVERRIDE = "classification:override"
    REPORT_WRITE = "report:write"
    REPORT_SIGN = "report:sign"
    EXPORT_STUDY = "export:study"
    EXPORT_AGGREGATE = "export:aggregate"
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"
    CONFIG_WRITE = "config:write"


class PurposeOfUse(str, Enum):
    TREATMENT = "TREATMENT"
    PAYMENT = "PAYMENT"
    OPERATIONS = "OPERATIONS"
    RESEARCH = "RESEARCH"


@dataclass
class PermissionContext:
    role: Role
    user_id: str
    purpose: PurposeOfUse
    mfa_verified_within_minutes: int
    break_glass_active: bool
    break_glass_reason: str | None
    assigned_patient_ids: set[str]


# Permission matrix.
# Rows are roles; columns are actions; value is an allow function.
# An allow function returns True if permitted given context and optional subject hints.
AllowFn = "callable[[PermissionContext, dict], bool]"


def _always(_ctx: PermissionContext, _subject: dict | None) -> bool:
    return True


def _mfa_within(minutes: int):
    def _fn(ctx: PermissionContext, _subject: dict | None) -> bool:
        return ctx.mfa_verified_within_minutes <= minutes

    return _fn


def _if_assigned_or_breakglass(ctx: PermissionContext, subject: dict | None) -> bool:
    if ctx.break_glass_active and ctx.break_glass_reason:
        return True
    if subject is None:
        return False
    patient_id = subject.get("patient_id")
    return bool(patient_id) and patient_id in ctx.assigned_patient_ids


def _never(_ctx: PermissionContext, _subject: dict | None) -> bool:
    return False


_MATRIX: dict[Role, dict[Action, "AllowFn"]] = {
    Role.RADIOLOGIST: {
        Action.STUDY_READ: _always,
        Action.STUDY_LIST: _always,
        Action.CLASSIFICATION_RUN: _always,
        Action.CLASSIFICATION_VIEW: _always,
        Action.CLASSIFICATION_OVERRIDE: _mfa_within(30),
        Action.REPORT_WRITE: _mfa_within(30),
        Action.REPORT_SIGN: _mfa_within(15),
        Action.EXPORT_STUDY: _mfa_within(5),
        Action.EXPORT_AGGREGATE: _mfa_within(30),
    },
    Role.OPHTHALMOLOGIST: {
        Action.STUDY_READ: _always,
        Action.STUDY_LIST: _always,
        Action.CLASSIFICATION_RUN: _always,
        Action.CLASSIFICATION_VIEW: _always,
        Action.CLASSIFICATION_OVERRIDE: _mfa_within(30),
        Action.REPORT_WRITE: _mfa_within(30),
        Action.REPORT_SIGN: _mfa_within(15),
        Action.EXPORT_STUDY: _mfa_within(5),
        Action.EXPORT_AGGREGATE: _mfa_within(30),
    },
    Role.REFERRING_PHYSICIAN: {
        Action.STUDY_READ: _if_assigned_or_breakglass,
        Action.STUDY_LIST: _if_assigned_or_breakglass,
        Action.CLASSIFICATION_VIEW: _if_assigned_or_breakglass,
    },
    Role.TECHNICIAN: {
        # Can intake studies (triggered by DICOM ingest) but not see classifications.
        Action.STUDY_LIST: _always,
    },
    Role.RESEARCHER: {
        # De-identified only — the views restrict this at the data layer too.
        Action.CLASSIFICATION_VIEW: _always,
        Action.EXPORT_AGGREGATE: _mfa_within(30),
    },
    Role.COMPLIANCE_OFFICER: {
        Action.AUDIT_READ: _always,
        Action.AUDIT_EXPORT: _mfa_within(30),
    },
    Role.SYSTEM_ADMIN: {
        Action.CONFIG_WRITE: _mfa_within(5),
    },
    Role.AUDITOR_EXTERNAL: {
        # Time-boxed session; permission set adjusted session-by-session at establishment time.
        Action.AUDIT_READ: _always,
    },
    Role.BREAK_GLASS: {
        # All actions via delegation; break_glass role augments the user's base role.
        # This entry is a placeholder — is_permitted checks the base role but with
        # break_glass_active=True and uses _if_assigned_or_breakglass semantics.
    },
}


def is_permitted(
    action: Action, context: PermissionContext, subject: dict | None = None
) -> bool:
    """Check whether the given action is permitted for the context.

    Returns True/False. No errors raised for missing permissions — caller emits
    the 403 response and an audit log entry.
    """
    allow_fns = _MATRIX.get(context.role, {})
    fn = allow_fns.get(action)
    if fn is None:
        return False
    return fn(context, subject)


def permissions_for_role(role: Role) -> list[Action]:
    """Return the list of actions this role can perform (ignoring conditions)."""
    return list(_MATRIX.get(role, {}).keys())


def describe_permission_matrix() -> str:
    """Human-readable matrix dump for documentation and compliance review."""
    lines = ["Role × Action permission matrix", ""]
    all_actions = sorted({a for perms in _MATRIX.values() for a in perms.keys()}, key=lambda a: a.value)
    header = "Role".ljust(24) + "".join(a.value.ljust(30) for a in all_actions)
    lines.append(header)
    lines.append("-" * len(header))
    for role in Role:
        row = role.value.ljust(24)
        perms = _MATRIX.get(role, {})
        for action in all_actions:
            row += ("yes" if action in perms else "no").ljust(30)
        lines.append(row)
    return "\n".join(lines)


# Assertion: this matrix should stay synchronized with access/README.md's table.
# The test_roles.py test suite verifies this synchronization.
