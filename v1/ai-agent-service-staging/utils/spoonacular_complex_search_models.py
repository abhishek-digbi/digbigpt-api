from enum import Enum
from typing import List, Optional, Sequence, Union, Type

from pydantic import BaseModel, Field, ConfigDict, field_validator


# ---------- Enumerations (strings are the EXACT API tokens) ----------


class Cuisine(str, Enum):
    african = "african"
    american = "american"
    british = "british"
    cajun = "cajun"
    caribbean = "caribbean"
    chinese = "chinese"
    eastern_european = "eastern european"
    french = "french"
    german = "german"
    greek = "greek"
    indian = "indian"
    irish = "irish"
    italian = "italian"
    japanese = "japanese"
    jewish = "jewish"
    korean = "korean"
    latin_american = "latin american"
    mediterranean = "mediterranean"  # sometimes grouped under “middle eastern/mediterranean” in docs
    mexican = "mexican"
    middle_eastern = "middle eastern"
    nordic = "nordic"
    southern = "southern"
    spanish = "spanish"
    thai = "thai"
    vietnamese = "vietnamese"


class Diet(str, Enum):
    gluten_free = "gluten free"
    ketogenic = "ketogenic"
    vegetarian = "vegetarian"
    lacto_vegetarian = "lacto vegetarian"
    ovo_vegetarian = "ovo vegetarian"
    vegan = "vegan"
    pescetarian = "pescetarian"
    paleo = "paleo"
    primal = "primal"
    low_fodmap = "low fodmap"
    whole30 = "whole30"


class Intolerance(str, Enum):
    dairy = "dairy"
    egg = "egg"
    gluten = "gluten"
    grain = "grain"
    peanut = "peanut"
    sesame = "sesame"
    seafood = "seafood"
    shellfish = "shellfish"
    soy = "soy"
    sulfite = "sulfite"
    tree_nut = "tree nut"
    wheat = "wheat"


class MealType(str, Enum):
    main_course = "main course"
    side_dish = "side dish"
    dessert = "dessert"
    appetizer = "appetizer"
    salad = "salad"
    bread = "bread"
    breakfast = "breakfast"
    soup = "soup"
    beverage = "beverage"
    sauce = "sauce"
    drink = "drink"
    marinade = "marinade"
    fingerfood = "fingerfood"
    snack = "snack"


class SpoonacularComplexSearchRequest(BaseModel):
    """
    Pydantic model for Spoonacular's Complex Search endpoint (request params).

    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    # Text query
    query: Optional[str] = Field(
        None,
        description=(
            "Natural-language recipe search query. Avoid meta terms that would not appear in a recipe title "
            "or description (e.g., 'recipes', 'menu ideas', 'meal plans'); focus on the dish or ingredients."
        ),
    )

    # Cuisine filters
    cuisines: Optional[List[Cuisine]] = Field(
        None,
        alias="cuisine",
        description="The cuisine(s) of the recipes. One or more, comma separated (will be interpreted as 'OR').",
    )
    exclude_cuisines: Optional[List[Cuisine]] = Field(
        None,
        alias="excludeCuisine",
        description="The cuisine(s) the recipes must not match. One or more, comma separated (will be interpreted as 'AND').",
    )

    # Diet filters
    diet: Optional[List[Diet]] = Field(
        None,
        description="The diet(s) for which the recipes must be suitable. You can specify multiple with comma meaning AND connection. You can specify multiple diets separated with a pipe | meaning OR connection. For example diet=gluten free,vegetarian means the recipes must be both, gluten free and vegetarian. If you specify diet=vegan|vegetarian, it means you want recipes that are vegan OR vegetarian.",
    )

    # Other filters
    intolerances: Optional[List[Intolerance]] = Field(
        None,
        description="A comma-separated list of intolerances. All recipes returned must not contain ingredients that are not suitable for people with the intolerances entered.",
    )
    include_ingredients: Optional[List[str]] = Field(
        None,
        alias="includeIngredients",
        description=(
            "A comma-separated list of literal ingredients (single foods or edible items) that must appear. "
            "Do not include dietary goals, cuisines, dish types, health benefits, or descriptive phrases—"
            "stick to concrete ingredients only. Prefer three or fewer ingredients to keep the search focused."
        ),
    )
    exclude_ingredients: Optional[List[str]] = Field(
        None,
        alias="excludeIngredients",
        description="A comma-separated list of ingredients or ingredient types that the recipes must not contain.",
    )
    type: Optional[MealType] = Field(None, description="The type of recipe.")
    max_carbs: Optional[float] = Field(
        None,
        alias="maxCarbs",
        ge=0,
        description="Maximum carbohydrates (grams) per serving.",
    )
    number: int = Field(1, ge=1, le=3, description="The number of expected results")

    # ---------- Normalizers so agents can pass flexible strings ----------

    @staticmethod
    def _norm_token(s: str) -> str:
        s = (s or "").strip().lower()
        # unify hyphens/extra spaces for known tokens
        s = s.replace("-", " ")
        # normalize common aliases
        return {
            "lacto vegetarian": "lacto vegetarian",
            "ovo vegetarian": "ovo vegetarian",
            "low fodmap": "low fodmap",
            "whole 30": "whole30",
        }.get(s, s)

    @classmethod
    def _coerce_enum_list(
        cls, v: Optional[Sequence[Union[str, Enum]]], enum_cls: Type[Enum]
    ) -> Optional[List[Enum]]:
        if v is None:
            return None
        out: List[Enum] = []
        for item in v:
            if isinstance(item, enum_cls):
                out.append(item)
            elif isinstance(item, str):
                tok = cls._norm_token(item)
                # try direct enum match on value
                for e in enum_cls:
                    if tok == e.value:
                        out.append(e)
                        break
                else:
                    raise ValueError(
                        f"Unsupported value '{item}' for {enum_cls.__name__}"
                    )
            else:
                raise ValueError(f"Invalid type for {enum_cls.__name__}: {type(item)}")
        return out or None

    @field_validator("cuisines", mode="before")
    @classmethod
    def _coerce_cuisines(cls, v):
        return cls._coerce_enum_list(v, Cuisine)

    @field_validator("exclude_cuisines", mode="before")
    @classmethod
    def _coerce_exclude_cuisines(cls, v):
        return cls._coerce_enum_list(v, Cuisine)

    @field_validator("diet", mode="before")
    @classmethod
    def _coerce_diet(cls, v):
        return cls._coerce_enum_list(v, Diet)

    @field_validator("intolerances", mode="before")
    @classmethod
    def _coerce_intolerances(cls, v):
        return cls._coerce_enum_list(v, Intolerance)

    @field_validator("type", mode="before")
    @classmethod
    def _coerce_type(cls, v):
        return cls._coerce_enum_list([v], MealType)[0] if v else v

    @field_validator("include_ingredients", "exclude_ingredients", mode="before")
    @classmethod
    def _strip_items(cls, v):
        if v is None:
            return v
        return [item.strip() for item in v if isinstance(item, str) and item.strip()]

    @field_validator("query", mode="before")
    @classmethod
    def _strip_scalar(cls, v):
        return v.strip() if isinstance(v, str) else v

    # ---------- Export helper ----------

    def to_query_params(self) -> dict:
        """
        Convert this model into a dict suitable for requests, using the exact
        Spoonacular parameter names and list-join conventions.
        """
        params: dict = {}

        if self.query:
            params["query"] = self.query

        if self.cuisines:
            params["cuisine"] = ",".join(e.value for e in self.cuisines)

        if self.exclude_cuisines:
            params["excludeCuisine"] = ",".join(e.value for e in self.exclude_cuisines)

        if self.diet:
            params["diet"] = ",".join(e.value for e in self.diet)

        if self.intolerances:
            params["intolerances"] = ",".join(e.value for e in self.intolerances)

        if self.include_ingredients:
            params["includeIngredients"] = ",".join(self.include_ingredients)

        if self.exclude_ingredients:
            params["excludeIngredients"] = ",".join(self.exclude_ingredients)

        if self.type:
            params["type"] = self.type.value

        if self.max_carbs is not None:
            params["maxCarbs"] = self.max_carbs

        if self.number is not None:
            params["number"] = self.number

        return params
