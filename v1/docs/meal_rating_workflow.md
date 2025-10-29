# Meal Rating Workflow

The Meal Rating feature analyzes photos and descriptions of meals to provide nutritional feedback.

1. **API Layer** – `POST /api/meal-rating` validates the payload and enqueues background processing via `process_meal_image_task`.
2. **Image Analysis** – If an image URL is present, `VisionAgent.analyze_image_v2` (LangFuse prompt `MEAL_PHOTO_ANALYZER_AGENT`) detects food items and stores the result.
3. **Description Enrichment** – `enrich_with_description_task` combines the user-provided description with any vision results using `NutritionAgent.update_wdesc_v2`.
4. **Final Feedback** – `NutritionAgent.finalize_feedback_task` retrieves user health data, computes ND and meal scores, and generates LLM feedback (`MEAL_FEEDBACK_AGENT`). Results are logged and sent to Digbi through the configured callback.
5. **Error Handling** – Failures are logged and reported to the client with appropriate status codes.

The workflow relies on LangFuse prompt variables which are resolved automatically by `AiCoreService` and `LangFuseService` before each agent call.
