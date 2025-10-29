from typing import Any
import atexit

from langfuse import Langfuse



class LangFuseService:
    def __init__(self, env, secret_key, public_key, host):
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
        cache_ttl_seconds = 600 if label == "production" else 0
        return self.langfuse.get_prompt(key, label=label, cache_ttl_seconds=cache_ttl_seconds)

    def get_variables(self, key, user_type):
        label = self._get_label(user_type)
        promptClient = self._get_prompt(key, label)
        return promptClient.variables

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

            if merged_context:
                # Compile the prompt using merged context
                prompt = prompt_template.compile(**merged_context)
            else:
                prompt = prompt_template.prompt

            return prompt
        except Exception as e:
            raise Exception(f"An error occurred while generating the {prompt_key} prompt:\n {e}")

    def shutdown(self):
        """Gracefully shut down the Langfuse client."""
        try:
            self.langfuse.shutdown()
        except Exception:
            pass
