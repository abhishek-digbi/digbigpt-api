from typing import Any, List, Optional, Union, Generic, TypeVar, Dict
from pydantic import BaseModel
from agent_core.config.schema import AgentConfig

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    message: str
    status: int
    timestamp: int
    result: Optional[T] = None


# ----- Agent Endpoints -----
class RunAgentRequest(BaseModel):
    query_id: Optional[str] = None
    query: Optional[str] = None
    feature_context: Optional[str] = None
    user_type: Optional[str] = None
    conversation_history: Optional[dict] = None
    data: Optional[dict] = None
    user_token: Optional[str] = None
    tools: Optional[List[dict]] = None


RunAgentResponse = ApiResponse[Any]

CreateAgentResponse = ApiResponse[Any]
UpdateAgentResponse = ApiResponse[Any]
AgentLogsResponse = ApiResponse[List[Any]]
AgentListResponse = ApiResponse[List[AgentConfig]]


class AgentCreateRequest(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    provider: Optional[str] = "openai"
    model: Optional[str] = "gpt-4o"
    langfuse_prompt_key: Optional[str] = None
    text_format: Optional[str] = None
    assistant_id: Optional[str] = None
    instructions: Optional[str] = None
    vector_store_ids: Optional[List[str]] = None
    tools: Optional[List[str]] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None


AgentUpdateRequest = AgentCreateRequest


# ----- Ask Digbi -----
class AppContext(BaseModel):
    screen_info: Optional[str] = None
    entity_id: Optional[str] = None


class ConversationMessage(BaseModel):
    sender: Optional[str] = None
    content: Optional[str] = None
    timestamp: Optional[Union[str, int]] = None


class ConversationContext(BaseModel):
    summary: Optional[str] = None
    recent_messages: List[ConversationMessage] = []


class AskDigbiContext(BaseModel):
    app: Optional[AppContext] = None
    conversation: Optional[ConversationContext] = None


class AskDigbiRequest(BaseModel):
    user_token: str
    user_type: Optional[str] = "PRODUCTION"
    query_id: Optional[Union[str, int]] = None
    query: str
    context: Optional[AskDigbiContext] = None


AskDigbiResponse = ApiResponse[Any]


# ----- Meal Rating -----
class MealContext(BaseModel):
    phase: Optional[str] = None
    cgm_in_use: Optional[bool] = None
    cgm_bad_peak: Optional[bool] = None
    cgm_bad_recovery: Optional[bool] = None
    meal_time: Optional[str] = None
    cgm_data_pending: Optional[bool] = None


class MealInfo(BaseModel):
    image_id: Optional[Union[int, str]] = None
    food_post_id: Optional[Union[int, str]] = None
    image_url: Optional[str] = None
    cgm_meal_context: Optional[MealContext] = None
    is_spoonacular_product_details: Optional [bool] = None
    meal_description: Optional[Any] = None


class MetaData(BaseModel):
    feature_tag: Optional[str] = None


class UserInfo(BaseModel):
    user_token: Optional[str] = None
    user_type: Optional[str] = None


class MealRatingRequest(BaseModel):
    meal_info: Optional[MealInfo] = None
    meta_data: Optional[MetaData] = None
    user_info: Optional[UserInfo] = None
    askMealEvaluation: Optional[bool] = False


MealRatingResponse = ApiResponse[Any]
MealRatingLogsResponse = ApiResponse[List[Any]]

# ----- Vector Store -----
VectorStoreFileResponse = ApiResponse[Any]


# ----- Tools -----
class ExecuteToolRequest(BaseModel):
    user_token: Optional[str] = None
    use_cache: Optional[bool] = None
    args: Optional[Dict[str, Any]] = None


ExecuteToolResponse = ApiResponse[Any]


class VariablesRequest(BaseModel):
    user_token: str
    variables: List[str]
    use_cache: Optional[bool] = True
    last_num_days: Optional[int] = None


VariablesResponse = ApiResponse[Dict[str, Any]]
