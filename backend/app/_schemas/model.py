"""Model config schemas."""
from pydantic import BaseModel, Field, computed_field
from .common import IsoDT


class ModelConfigCreate(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    provider: str = "ollama"
    base_url: str | None = None
    api_key: str | None = None
    model_name: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.9
    is_default: bool = False
    is_active: bool = True
    description: str | None = None


class ModelConfigUpdate(BaseModel):
    name: str | None = None
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model_name: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    is_default: bool | None = None
    is_active: bool | None = None
    description: str | None = None


class ModelConfigOut(BaseModel):
    id: str
    name: str
    provider: str
    base_url: str | None = None
    api_key: str | None = None
    model_name: str
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.9
    is_default: bool = False
    is_active: bool = True
    description: str | None = None
    created_at: IsoDT = None
    updated_at: IsoDT = None
    model_config = {"from_attributes": True}

    @computed_field
    @property
    def is_configured(self) -> bool:
        if self.provider == "ollama":
            return bool(self.model_name)
        if self.provider == "ollama_cloud":
            return bool(self.base_url and self.api_key and self.model_name)
        if self.provider in {"lmstudio", "cc_switch"}:
            return bool(self.base_url and self.model_name)
        return bool(self.base_url and self.api_key and self.model_name)


class ModelListRequest(BaseModel):
    provider: str = "ollama"
    base_url: str | None = None
    api_key: str | None = None
    model_name: str = ""


class ModelTestResult(BaseModel):
    success: bool
    message: str
    response_preview: str | None = None
    duration_ms: int | None = None


class ListModelsResult(BaseModel):
    success: bool
    message: str
    models: list[str] = []
    provider_type: str = ""
    current_model: str = ""


class DiscoveredProvider(BaseModel):
    provider: str
    base_url: str
    models: list[str] = []
    reachable: bool = True
    note: str | None = None


class AutoDiscoverResult(BaseModel):
    providers: list[DiscoveredProvider] = []
