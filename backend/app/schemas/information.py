import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

SourceType = Literal["announcement", "news", "social", "analyst_opinion", "user_note", "unknown"]
RelationType = Literal[
    "directly_related",
    "indirectly_related",
    "mentioned",
    "compared",
    "supply_chain",
    "competitor",
    "unknown",
]


class StrictAnalysisModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClaimItem(StrictAnalysisModel):
    claim: str
    evidence_text: str
    confidence: float = Field(ge=0, le=1)


class OpinionItem(StrictAnalysisModel):
    claim: str
    holder: str | None = None
    rationale: str | None = None
    time_horizon: str | None = None
    confidence: float = Field(ge=0, le=1)
    evidence_text: str


class RumorItem(StrictAnalysisModel):
    claim: str
    verification_needed: str
    confidence: float = Field(ge=0, le=1)
    evidence_text: str


class SentimentResult(StrictAnalysisModel):
    direction: Literal["positive", "negative", "neutral", "mixed", "unclear"]
    strength: Literal["low", "medium", "high"]
    target: str | None = None
    confidence: float = Field(ge=0, le=1)
    rationale: str


class SourceReliability(StrictAnalysisModel):
    level: Literal["high", "medium", "low", "unknown"]
    reasons: list[str]


class StockMentionResult(StrictAnalysisModel):
    symbol: str | None = None
    name: str | None = None
    relation_type: RelationType
    confidence: float = Field(ge=0, le=1)
    evidence_text: str


class EntityMentionResult(StrictAnalysisModel):
    entity_type: Literal[
        "company",
        "industry",
        "concept",
        "product",
        "person",
        "organization",
        "commodity",
        "policy",
        "location",
        "unknown",
    ]
    entity_name: str
    relation: str | None = None
    confidence: float = Field(ge=0, le=1)
    evidence_text: str


class RiskResult(StrictAnalysisModel):
    description: str
    severity: Literal["low", "medium", "high"]
    evidence_text: str


class VerificationResult(StrictAnalysisModel):
    description: str
    verification_type: str
    priority: Literal["low", "medium", "high"]
    evidence_needed: str


class InformationResearchTaskSuggestion(StrictAnalysisModel):
    task_type: Literal["verification", "observation", "follow_up", "missing_document", "user_note"]
    title: str
    reason: str
    priority: Literal["low", "medium", "high"] = "medium"
    related_fact_indexes: list[int] = Field(default_factory=list)
    suggested_due_date: str | None = None


class InformationObservationSuggestion(StrictAnalysisModel):
    title: str
    observation_condition: str
    verification_method: str
    priority: Literal["low", "medium", "high"] = "medium"
    related_fact_indexes: list[int] = Field(default_factory=list)
    suggested_due_date: str | None = None


class StructuredInformationAnalysis(StrictAnalysisModel):
    schema_version: str
    content_type: Literal[
        "announcement",
        "news_report",
        "analyst_opinion",
        "social_opinion",
        "rumor",
        "advertisement",
        "user_note",
        "mixed",
        "unknown",
    ]
    summary: str
    facts: list[ClaimItem]
    opinions: list[OpinionItem]
    rumors: list[RumorItem]
    sentiment: SentimentResult
    evidence_strength: Literal["strong", "medium", "weak", "insufficient"]
    uncertainty: Literal["low", "medium", "high"]
    source_reliability: SourceReliability
    key_claims: list[ClaimItem]
    confirmed_facts: list[ClaimItem] = Field(default_factory=list)
    key_changes: list[str] = Field(default_factory=list)
    affected_dimensions: list[
        Literal["policy", "industry", "company", "product", "finance", "market", "sentiment", "risk", "other"]
    ] = Field(default_factory=list)
    relation_to_focus_reason: Literal["direct", "indirect", "unrelated", "unable_to_determine"] = "unable_to_determine"
    stock_mentions: list[StockMentionResult]
    entity_mentions: list[EntityMentionResult]
    risks: list[RiskResult]
    verification_items: list[VerificationResult]
    suggested_research_tasks: list[InformationResearchTaskSuggestion] = Field(default_factory=list)
    suggested_observation_conditions: list[InformationObservationSuggestion] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    source_coverage: Literal["metadata_only", "partial_text", "full_text", "user_supplied", "unknown"] = "unknown"
    time_horizon: str | None = None
    limitations: list[str]


class ManualInformationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    text: str = Field(min_length=1)
    source_type: SourceType = "unknown"
    source_name: str | None = Field(default=None, max_length=200)
    published_at: datetime | None = None
    user_note: str | None = None
    related_stock_ids: list[uuid.UUID] = Field(default_factory=list)
    analyze_now: bool = False


class UrlInformationCreate(BaseModel):
    url: HttpUrl
    source_type: SourceType = "unknown"
    user_note: str | None = None
    related_stock_ids: list[uuid.UUID] = Field(default_factory=list)
    fetch_now: bool = True


class InformationPatch(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    user_note: str | None = None
    is_important: bool | None = None
    is_read: bool | None = None
    archived: bool | None = None


class InformationContentCreate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    text: str = Field(min_length=1)


class InformationAnalyzeRequest(BaseModel):
    force: bool = False


class StockRelationCreate(BaseModel):
    stock_id: uuid.UUID
    relation_type: RelationType = "directly_related"
    evidence_text: str | None = Field(default=None, max_length=500)


class StockRelationPatch(BaseModel):
    stock_id: uuid.UUID | None = None
    relation_type: RelationType | None = None
    relation_status: Literal["confirmed", "rejected"] | None = None
    evidence_text: str | None = Field(default=None, max_length=500)


class InformationSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_url: str | None
    normalized_url: str | None
    source_name: str | None
    author: str | None
    published_at: datetime | None
    fetched_at: datetime | None
    http_status: int | None
    content_type: str | None
    fetch_status: str


class InformationContentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content_version: int
    content_origin: str
    extracted_title: str | None
    extracted_text: str
    content_hash: str
    character_count: int
    extraction_method: str
    extraction_status: str
    created_at: datetime


class InformationAnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version_number: int
    schema_version: str
    prompt_version: str
    provider_config_id: uuid.UUID | None
    model_name: str | None
    analysis_status: str
    structured_result: dict
    input_content_hash: str | None
    created_at: datetime


class InformationStockRelationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    stock_id: uuid.UUID
    relation_origin: str
    relation_status: str
    relation_type: str
    confidence: float | None
    evidence_text: str | None
    reviewed_at: datetime | None


class InformationEntityMentionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_type: str
    entity_name: str
    relation: str | None
    confidence: float | None
    evidence_text: str | None
    origin: str
    status: str


class VerificationItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    description: str
    verification_type: str
    status: str
    priority: str | None
    evidence_needed: str | None
    user_note: str | None
    resolved_at: datetime | None


class InformationSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    input_type: str
    status: str
    source_type: str
    title: str | None
    user_note: str | None
    is_important: bool
    is_read: bool
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class InformationDetailOut(InformationSummaryOut):
    sources: list[InformationSourceOut]
    current_content: InformationContentOut | None
    latest_analysis: InformationAnalysisOut | None
    analysis_versions: list[InformationAnalysisOut]
    stock_relations: list[InformationStockRelationOut]
    entity_mentions: list[InformationEntityMentionOut]
    verification_items: list[VerificationItemOut]
    latest_ai_task_status: str | None = None
