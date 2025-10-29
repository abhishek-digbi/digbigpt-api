import json
import os
from typing import List, Dict, Any
from urllib.parse import quote

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from agent_core.config.logging_config import logger
from agent_core.services.ai_core_service import AiCoreService
from agent_core.services.model_context import ModelContext
from tools.services.typeform_service import (
    create_typeform_quiz,
    register_typeform_webhook,
)
from orchestrator.orchestrators.base_ask_digbi_agent import AskDigbiBaseAgent
from utils.env_loader import get_env_var

load_dotenv()


class Choice(BaseModel):
    ref: str = Field(
        ..., description="Unique identifier for the choice (e.g., 'a', 'b', 'c', 'd')"
    )
    label: str = Field(..., description="The text shown to the user for this choice")


class Properties(BaseModel):
    choices: List[Choice] = Field(
        ..., description="List of answer choices for the question"
    )
    randomize: bool = Field(
        ...,
        description="Indicates whether to randomize the order of choices (always False)",
    )


class Validations(BaseModel):
    required: bool = Field(
        ..., description="Indicates whether the question must be answered (always True)"
    )


class Question(BaseModel):
    ref: str = Field(
        ..., description="Unique question reference identifier (e.g., 'q1', 'q2')"
    )
    type: str = Field(..., description="Typeform field type, always 'multiple_choice'")
    title: str = Field(..., description="The actual question text shown to the user")
    properties: Properties = Field(
        ..., description="Contains the list of choices and choice behavior"
    )
    validations: Validations = Field(
        ..., description="Validation rules for the question"
    )
    correct_ref: str = Field(
        ..., description="The 'ref' of the correct choice in the choices array"
    )
    snippet: str = Field(
        ...,
        description="A one-sentence educational explanation of why this answer is correct",
    )


class Quiz(BaseModel):
    identifier: str = Field(
        ...,
        description="A unique identifier for this quiz. A combination of the user token and "
        "date time",
    )
    topic: str = Field(
        ..., description="The shared topic for all questions in this quiz"
    )
    questions: List[Question] = Field(
        ..., description="List of multiple-choice questions forming the quiz"
    )


class EdutainmentAgentGus(AskDigbiBaseAgent):
    DIGBI_URL = get_env_var("DIGBI_URL")

    def __init__(self, ai_core: AiCoreService):
        self.ai_core = ai_core
        self.agent_id = "EDUTAINMENT_AGENT_GUS"

    async def ask(self, ctx: ModelContext) -> dict[str, str]:
        logger.info(
            "Triggering Edutainment Agent Gus: user=%s qid=%s",
            ctx.user_token,
            ctx.query_id,
        )

        result: Quiz = await self.ai_core.run_agent(
            self.agent_id, ctx, output_type=Quiz
        )
        payload, answer_key = self.build_payload_and_logic(
            result.questions, result.topic, result.identifier
        )
        typeform_response = await create_typeform_quiz(payload)
        if typeform_response.status_code == 201:
            form_id = typeform_response.json()["id"]
            encoded_user_id = quote(ctx.user_token, safe="")
            webhook_url = (
                f"{EdutainmentAgentGus.DIGBI_URL}/api/v2/content-widgets/user/widget/QUIZ"
                f"/DAILY_EDUTAINMENT/{form_id}/submission?user_token={encoded_user_id}"
            )
            register_webhook_response = await register_typeform_webhook(
                form_id, webhook_url
            )
            if register_webhook_response.status_code in (200, 201):
                print("✅ Form created and webhook registered successfully!")
                typeform_base_url = get_env_var("TYPEFORM_BASE_URL")
                form_url = f"{typeform_base_url}/{form_id}"
                print("🔗 Public Form URL:", form_url)
                return {
                    "status": "success",
                    "id": form_id,
                    "link": form_url,
                    "message": "Created quiz successfully!",
                    "title": result.topic,
                    "answer_key": json.dumps(answer_key) if answer_key else "",
                }

            print("❌ Failed to register webhook")
            print("Status Code:", register_webhook_response.status_code)
            print("Error Response:", register_webhook_response.text)
            return {
                "status": "failure",
                "id": "",
                "link": "",
                "message": "Failed to register webhook",
                "title": "",
                "answer_key": None,
            }

        print("❌ Failed to create form")
        print("Status Code:", typeform_response.status_code)
        print("Error Response:", typeform_response.text)
        return {
            "status": "failure",
            "id": "",
            "link": "",
            "message": "Failed to create quiz",
            "title": "",
            "answer_key": None,
        }

    @staticmethod
    def build_payload_and_logic(
        questions: list[Question], topic: str, identifier: str
    ) -> (Dict[str, Any], Dict[str, str]):
        """
        Build the Typeform payload with questions, logic jumps, and explanatory snippets.
        """

        fields = []
        logic = []
        num_questions = len(questions)
        questions_with_answer = {}
        for idx, q in enumerate(questions):
            q_ref = q.ref
            correct = q.correct_ref
            # Question field
            fields.append(
                {
                    "ref": q_ref,
                    "type": "multiple_choice",
                    "title": q.title,
                    "properties": q.properties.model_dump(),
                    "validations": q.validations.model_dump(),
                }
            )
            # Determine correct label
            correct_label = next(
                (c.label for c in q.properties.choices if c.ref == correct), ""
            )
            questions_with_answer[q_ref] = {
                "text": q.title,
                "answer": correct,
                "snippet": q.snippet,
            }
            # Generate explanatory snippet
            snippet = q.snippet
            # Correct feedback
            fields.append(
                {
                    "ref": f"{q_ref}_correct",
                    "type": "statement",
                    "title": f"✅ Correct!\n\n💡 Explanation:\n{snippet}",
                    "properties": {"button_text": "Next", "hide_marks": True},
                }
            )
            # Incorrect feedback with correct answer
            fields.append(
                {
                    "ref": f"{q_ref}_incorrect",
                    "type": "statement",
                    "title": f"❌ Incorrect\nThe correct answer was \"{correct_label}\"\n\n💡 Explanation:\n{snippet}",
                    "properties": {"button_text": "Next", "hide_marks": True},
                }
            )
            # Logic: correct vs incorrect
            logic.append(
                {
                    "type": "field",
                    "ref": q_ref,
                    "actions": [
                        {
                            "action": "jump",
                            "details": {
                                "to": {"type": "field", "value": f"{q_ref}_correct"}
                            },
                            "condition": {
                                "op": "is",
                                "vars": [
                                    {"type": "field", "value": q_ref},
                                    {"type": "choice", "value": correct},
                                ],
                            },
                        },
                        {
                            "action": "jump",
                            "details": {
                                "to": {"type": "field", "value": f"{q_ref}_incorrect"}
                            },
                            "condition": {
                                "op": "is_not",
                                "vars": [
                                    {"type": "field", "value": q_ref},
                                    {"type": "choice", "value": correct},
                                ],
                            },
                        },
                    ],
                }
            )
            # After correct, jump to next question
            if idx < num_questions - 1:
                next_ref = questions[idx + 1].ref
                logic.append(
                    {
                        "type": "field",
                        "ref": f"{q_ref}_correct",
                        "actions": [
                            {
                                "action": "jump",
                                "details": {"to": {"type": "field", "value": next_ref}},
                                "condition": {"op": "always", "vars": []},
                            }
                        ],
                    }
                )
            else:
                # Last question: after correct snippet, jump to thank-you screen
                logic.append(
                    {
                        "type": "field",
                        "ref": f"{q_ref}_correct",
                        "actions": [
                            {
                                "action": "jump",
                                "details": {
                                    "to": {"type": "thankyou", "value": "custom_tys"}
                                },
                                "condition": {"op": "always", "vars": []},
                            }
                        ],
                    }
                )

        return {
            "type": "form",
            "workspace": {
                "href": os.getenv("TYPEFORM_WORKSPACE_URL")
            },
            "title": f"Quiz on topic : {topic}, identifier: {identifier}",
            "theme": {
                "href": os.getenv("TYPEFORM_THEMES_URL")
            },
            "settings": {
                "show_typeform_branding": False,
                "hide_navigation": True,
                "show_question_number": False
            },
            "fields": fields,
            "logic": logic,
            "thankyou_screens": [{
                "type": "thankyou_screen",
                "title": "Thanks for completing your personalized health quiz!",
                "ref": "custom_tys",
                "properties": {
                    "show_button": True,
                    "button_text": "Done",
                    "button_mode": "redirect",
                    "redirect_url": "https://member.digbihealth.com/",
                    "share_icons": False
                }
            }],
        }, questions_with_answer
