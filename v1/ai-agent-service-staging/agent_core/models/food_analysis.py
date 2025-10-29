from typing import List, Dict, Any, Optional, TypeVar, Type, Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator
from pydantic.json_schema import JsonValue
import json

T = TypeVar('T', bound='FoodAnalysisResult')

class FoodCategoryItem(BaseModel):
    foodCategory: str
    description: str
    novaClassification: str
    
    def model_dump(self, **kwargs) -> Dict[str, JsonValue]:
        return {
            "foodCategory": self.foodCategory,
            "description": self.description,
            "novaClassification": self.novaClassification
        }

class FoodAnalysisResult(BaseModel):
    """Represents the result of food analysis with dynamic threshold fields."""
    
    model_config = ConfigDict(
        extra='allow',  # Allow extra fields for dynamic threshold fields
        json_encoders={
            'FoodCategoryItem': lambda v: v.model_dump(),
        }
    )
    
    # Required fields
    foodCategories: List[FoodCategoryItem] = Field(default_factory=list)
    foodType: str = ""
    mealTime: str = ""
    ingredients: List[str] = Field(default_factory=list)
    ultraProcessed: bool = False
    
    # This will store all threshold fields dynamically
    threshold_fields: Dict[str, bool] = Field(default_factory=dict, exclude=True)
    
    @model_validator(mode='after')
    def extract_threshold_fields(self) -> 'FoodAnalysisResult':
        """Extract threshold fields from extra fields."""
        if hasattr(self, 'model_extra') and self.model_extra:
            threshold_fields = {}
            for key, value in self.model_extra.items():
                if isinstance(value, bool) and ("(Above Threshold:" in key or "(Below Threshold:" in key):
                    threshold_fields[key] = value
            
            # Remove threshold fields from extra fields
            for key in threshold_fields:
                delattr(self, key)
            
            # Update threshold fields
            self.threshold_fields.update(threshold_fields)
        return self
    
    def model_dump(self, *args, **kwargs) -> Dict[str, JsonValue]:
        """Convert the model to a dictionary, including threshold fields."""
        # Get the base model dump
        data = super().model_dump(*args, **kwargs)
        
        # Convert foodCategories to list of dicts
        if 'foodCategories' in data and data['foodCategories']:
            data['foodCategories'] = [
                item.model_dump() if hasattr(item, 'model_dump') else item
                for item in self.foodCategories
            ]
        
        # Remove the internal threshold_fields field if it exists
        data.pop('threshold_fields', None)
        
        # Add all threshold fields to the root level
        data.update(self.threshold_fields)
        
        return data
    
    def json(self, *args, **kwargs) -> str:
        """Convert the model to a JSON string."""
        return json.dumps(self.model_dump(), default=str, **kwargs)
    
    @classmethod
    def model_validate(cls: Type[T], obj: Any, **kwargs) -> T:
        """Create an instance from a dictionary, handling threshold fields."""
        if isinstance(obj, dict):
            # Extract threshold fields from the input
            threshold_fields = {}
            regular_data = {}
            
            for key, value in obj.items():
                if isinstance(value, bool) and ("(Above Threshold:" in key or "(Below Threshold:" in key):
                    threshold_fields[key] = value
                else:
                    regular_data[key] = value
            
            # Create the instance with regular data
            instance = super().model_validate(regular_data, **kwargs)
            
            # Set threshold fields
            instance.threshold_fields.update(threshold_fields)
            return instance
        return super().model_validate(obj, **kwargs)
    
    def get_threshold_field(self, field_name: str, default: Any = None) -> Any:
        """Safely get a threshold field value."""
        return self.threshold_fields.get(field_name, default)
    
    def set_threshold_field(self, field_name: str, value: bool) -> None:
        """Set a threshold field value."""
        self.threshold_fields[field_name] = value
    
    def update_threshold_fields(self, fields: Dict[str, bool]) -> None:
        """Update multiple threshold fields at once."""
        self.threshold_fields.update(fields)
    
    # For backward compatibility
    @classmethod
    def from_dict(cls: Type[T], data: dict) -> T:
        """Create an instance from a dictionary."""
        return cls.model_validate(data)
    
    def to_dict(self) -> dict:
        """Convert the instance to a dictionary."""
        return self.model_dump()
