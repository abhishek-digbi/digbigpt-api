"""Shared models used by support agent integrations."""

from enum import Enum


class KitRegistrationIntent(str, Enum):
    """Classifier output indicating whether the response suggests kit registration."""

    REGISTER = "REGISTER"
    DO_NOT_REGISTER = "DO_NOT_REGISTER"
    NONE = "NONE"


class InviteDependentIntent(str, Enum):
    """Classifier output indicating whether to invite an eligible dependent."""

    TRUE = "TRUE"
    FALSE = "FALSE"
