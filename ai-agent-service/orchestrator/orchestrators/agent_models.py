from dataclasses import dataclass, field
from typing import Annotated, List, Any, Dict, Optional, Literal
from pydantic import BaseModel, Field

from agent_core.models.support_intents import (
    InviteDependentIntent,
    KitRegistrationIntent,
)


@dataclass
class Action:
    """Encapsulates an agent routing action."""
    action: str
    message: str
    agent: str
    # Optional file filter hints for downstream agent calls
    file_filters: Optional[Dict[str, Any]] = None
    # Optional revised query produced by a classifier/reranker
    revised_query: str | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Action':
        return cls(
            action=data.get('action', ''),
            agent=data.get('agent', ''),
            message=data.get('message', ''),
            file_filters=data.get('file_filters'),
            revised_query=data.get('revised_query'),
        )

    def to_dict(self) -> Dict[str, Any]:
        result = {
            'action': self.action,
            'agent': self.agent,
            'message': self.message,
        }
        if self.revised_query is not None:
            result['revised_query'] = self.revised_query
        if self.file_filters is not None:
            result['file_filters'] = self.file_filters
        return result


@dataclass
class AgentRequest:
    """High-level request model for coordinating external agents."""
    actions: List[Action]
    details: str
    language: str | None = None
    status: str | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentRequest':
        actions_list = data.get('actions', [])
        actions = [Action.from_dict(item) for item in actions_list]
        details = data.get('details', '')
        language = data.get('language')
        return cls(actions=actions, details=details, language=language)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'actions': [action.to_dict() for action in self.actions],
            'details': self.details,
            'language': self.language,
        }

    def add_action(self, action: Action) -> None:
        self.actions.append(action)


class KeyValue(BaseModel):
    key: str = Field(description="name of any additional property which might be required")
    value: str = Field(description="value of any additional property which might be required")


class Resource(BaseModel):
    id: Optional[str]
    title: Optional[str] = Field(description="The resource title, for example - 'Introduction video'")
    url: Optional[str]
    description: Optional[str] = Field(
        description=(
            "For example - This video walks you through what's inside your report "
            "what each section means, and how to use it to take action on your health."
        )
    )
    additional_data: Optional[List[KeyValue]]


class InteractiveComponent(BaseModel):
    id: Optional[str] = Field(default=None, description="unique identifier")
    icon: Optional[str] = Field(default=None)
    color: Optional[str] = Field(default=None)
    display_text: str = Field(
        ...,
        description="One word display label for the interactive component or button",
    )
    screen_name: Literal["VideoPopUpScreen", "Recipe", "InviteDependent"] = Field(
        ...,
        description=(
            "if the action is supposed to show a video use VideoPopUpScreen, "
            "if action is supposed to open a recipe page use Recipe, "
            "if the user has an eligible dependent to invite use InviteDependent"
        ),
    )
    type: Literal["ROUTE", "SLIDEUP"] = Field(
        ...,
        description="ROUTE by default, SLIDEUP when screen_name is InviteDependent",
    )
    data: Optional[List[Resource]] = None


class VideoButton(InteractiveComponent):
    display_text: str = Field(
        ...,
        description="One word display label for the video",
    )
    screen_name: Literal["VideoPopUpScreen"] = Field(
        ...,
        description=(
            "if the action is supposed to show a video use VideoPopUpScreen, "
        ),
    )
    type: Literal["ROUTE"] = Field(
        ...,
        description="ROUTE by default",
    )


class Meta(BaseModel):
    actions: List[InteractiveComponent] = Field(default_factory=list)


class VideoMeta(BaseModel):
    actions: List[VideoButton] = Field(default_factory=list)


class BasicAgentResponse(BaseModel):
    status: str
    message: str


class ProgramDetailsAgentResponse(BasicAgentResponse):
    program_details: Dict[str, str] = Field(...)


class AgentResponse(BasicAgentResponse):
    meta: Meta = Field(default_factory=Meta)


class SupportAgentResponse(BasicAgentResponse):
    kit_registration_intent: Annotated[
        KitRegistrationIntent,
        Field(
            description=(
                "REGISTER if explicitly asking to register a kit; DO_NOT_REGISTER if explicitly "
                "asking not to; NONE otherwise."
            ),
            examples=["NONE"],
        ),
    ] = KitRegistrationIntent.NONE
    invite_dependent_intent: Annotated[
        InviteDependentIntent,
        Field(
            description=(
                "TRUE when the response offers to invite an eligible dependent; FALSE otherwise."
            ),
            examples=["FALSE"],
        ),
    ] = InviteDependentIntent.FALSE


class SummarizerAgentResponse(BasicAgentResponse):
    """Structured response for summarizer agent results."""

    message_references_a_video: bool = Field(
        ...,
        description="True when the message references a video for the user, does not care about the meta field",
    )
    meta: VideoMeta = Field(default_factory=VideoMeta)


class VideoRecommendationResult(BaseModel):
    """Structured output for VIDEO_RECOMMENDER_AGENT responses."""

    video: Optional[InteractiveComponent] = Field(
        default=None,
        description="Interactive component representing the recommended video, if any.",
    )
    explanation: Optional[str] = Field(
        default=None,
        description="Reason why this video was selected or why no video was returned.",
    )


@dataclass
class AgentRequestV2:
    """High-level request model for coordinating external agents."""
    actions: List[Action]
    details: str
    data_to_use: Dict[str, Any] = field(default_factory=dict)
    language: str | None = None
    status: str | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentRequestV2':
        actions_list = data.get('actions', [])
        actions = [Action.from_dict(item) for item in actions_list]
        details = data.get('details', '')
        language = data.get('language')
        data_to_use = data.get('data_to_use', {})
        return cls(
            actions=actions,
            details=details,
            data_to_use=data_to_use,
            language=language,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'actions': [action.to_dict() for action in self.actions],
            'details': self.details,
            'language': self.language,
            'data_to_use': self.data_to_use,
        }

    def add_action(self, action: Action) -> None:
        self.actions.append(action)
