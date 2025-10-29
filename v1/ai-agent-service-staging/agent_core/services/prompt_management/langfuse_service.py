from typing import Any, Optional
import atexit
import os
import logging

try:
    from langfuse import Langfuse  # type: ignore
except Exception:
    Langfuse = None  # Fallback when SDK not available



logger = logging.getLogger(__name__)


class LangFuseService:
    def __init__(self, env, secret_key: Optional[str], public_key: Optional[str], host: Optional[str]):
        disabled = os.getenv("LANGFUSE_DISABLED", "").strip().lower() in {"1", "true", "yes"}
        missing = not secret_key or not public_key or not host or Langfuse is None

        if disabled or missing:
            self.langfuse = None
            reason = "disabled via LANGFUSE_DISABLED" if disabled else "missing credentials or SDK"
            logger.warning("Langfuse is disabled (%s). Prompts will be used without Langfuse.", reason)
        else:
            self.langfuse = Langfuse(secret_key=secret_key, public_key=public_key, host=host)
        self.env = env
        atexit.register(self.shutdown)

    def _get_label(self, user_type):
        if user_type == "" or user_type is None:
            user_type='PRODUCTION'
        if self.env == 'DEVELOPMENT':
            return 'latest'
        elif self.env == 'STAGING':
            return 'staging'
        elif self.env == 'PRODUCTION':
            return user_type.lower()
        return 'production'  # default

    def _get_prompt(self, key, label):
        if self.langfuse is None:
            class _DummyPrompt:
                variables = {}
                prompt = key
                def compile(self, **kwargs):
                    return key
            return _DummyPrompt()

        cache_ttl_seconds = 600 if label == "production" else 0
        return self.langfuse.get_prompt(key, label=label, cache_ttl_seconds=cache_ttl_seconds)

    def get_variables(self, key, user_type):
        label = self._get_label(user_type)
        promptClient = self._get_prompt(key, label)
        return getattr(promptClient, "variables", {}) or {}

    def generate_prompt(self, user_type: str, prompt_key: str, *context_dicts: dict):
        """
            Generate a generic prompt based on multiple context dictionaries.

            :param type:
            :param user_type: BETA or Production
            :param prompt_key: The type of prompt to generate (e.g., "feedback", "recommendation", "summary").
            :param context_dicts: Any number of dictionaries containing contextual data.
            :return: The compiled prompt as a string.
            """
        try:
            # Merge all provided context dictionaries (later ones override earlier ones)
            merged_context: dict[str, Any] = {}
            for context in context_dicts:
                if isinstance(context, dict):
                    merged_context.update(context)

            # Determine user type and label dynamically
            label = self._get_label(user_type)

            # Retrieve the prompt template
            prompt_template = self._get_prompt(prompt_key, label)
            # print('prompt variables:', prompt_template.variables)

            if prompt_template is None:
                raise ValueError("Prompt template cannot be an empty string")

            if hasattr(prompt_template, "compile"):
                if merged_context:
                    return prompt_template.compile(**merged_context)
                return getattr(prompt_template, "prompt", prompt_key)

            # Fallback when disabled
            return prompt_key
        except Exception as e:
            raise Exception(f"An error occurred while generating the {prompt_key} prompt:\n {e}")

    def shutdown(self):
        """Gracefully shut down the Langfuse client."""
        try:
            if self.langfuse is not None:
                self.langfuse.shutdown()
        except Exception:
            pass
