from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AIGamifySourceType(str, Enum):
    MATERIAL = "material"
    QUESTION = "question"
    RAW_TEXT = "raw_text"


class AIGamifyTargetLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class AIGamifyStyle(str, Enum):
    QUEST = "quest"
    MISSION = "mission"
    CHALLENGE = "challenge"
    STORY = "story"


class AIGamifyTone(str, Enum):
    NEUTRAL = "neutral"
    FRIENDLY = "friendly"
    ENERGETIC = "energetic"


class AIGamifyJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    APPLIED = "applied"


class AIGamifyApplyMode(str, Enum):
    REPLACE = "replace"
    APPEND = "append"


class AIGamifyTargetType(str, Enum):
    MATERIAL = "material"
    QUESTION = "question"


class AIGamifyRequest(BaseModel):
    source_type: AIGamifySourceType
    source_id: int | None = None
    raw_text: str | None = None
    target_level: AIGamifyTargetLevel | None = None
    language: str = "ru"
    style: AIGamifyStyle | None = None
    tone: AIGamifyTone | None = None
    constraints: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_source(self) -> "AIGamifyRequest":
        if self.source_type == AIGamifySourceType.RAW_TEXT:
            if not self.raw_text or not self.raw_text.strip():
                raise ValueError("raw_text is required when source_type=raw_text")
            return self

        if self.source_id is None:
            raise ValueError("source_id is required for material/question source types")
        return self


class AIGamifyRewards(BaseModel):
    xp: int = 0
    badges: list[str] = Field(default_factory=list)


class AIGamifyDraft(BaseModel):
    draft_title: str
    story_frame: str
    task_goal: str
    game_rules: list[str] = Field(default_factory=list)
    hints: list[str] = Field(default_factory=list)
    rewards: AIGamifyRewards = Field(default_factory=AIGamifyRewards)
    acceptance_criteria: list[str] = Field(default_factory=list)
    teacher_notes: str | None = None


class AIGamifyCreateResponse(BaseModel):
    job_id: int
    status: AIGamifyJobStatus = AIGamifyJobStatus.PENDING


class AIGamifyUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class AIGamifyJobRead(BaseModel):
    job_id: int
    status: AIGamifyJobStatus
    input: AIGamifyRequest | None = None
    draft: AIGamifyDraft | None = None
    error: str | None = None
    model: str | None = None
    provider: str | None = None
    usage: AIGamifyUsage | None = None
    latency_ms: int | None = None


class AIGamifyJobListRead(BaseModel):
    items: list[AIGamifyJobRead]
    limit: int
    offset: int


class AIGamifyOpsMetricsRead(BaseModel):
    queued_jobs: int = 0
    dead_letter_jobs: int = 0
    jobs_processed: int = 0
    jobs_completed: int = 0
    jobs_failed: int = 0
    jobs_retried: int = 0
    jobs_semantic_fallback_used: int = 0


class AIGamifyDLQEntryRead(BaseModel):
    queue_index: int
    job_id: int | None = None
    error: str | None = None
    raw_payload: str


class AIGamifyDLQListRead(BaseModel):
    items: list[AIGamifyDLQEntryRead]
    limit: int
    offset: int
    total: int


class AIGamifyDLQRequeueRead(BaseModel):
    queue_index: int
    job_id: int
    status: AIGamifyJobStatus


class AIGamifyDLQDiscardRead(BaseModel):
    queue_index: int
    removed: bool


class AIGamifyDLQBatchActionRequest(BaseModel):
    max_items: int = Field(default=20, ge=1, le=500)


class AIGamifyDLQBatchActionRead(BaseModel):
    scanned: int
    requeued: int = 0
    discarded: int = 0
    skipped: int = 0
    failures: list[str] = Field(default_factory=list)


class AIGamifyApplyRequest(BaseModel):
    target_type: AIGamifyTargetType | None = None
    target_id: int | None = None
    apply_mode: AIGamifyApplyMode = AIGamifyApplyMode.APPEND

    @model_validator(mode="after")
    def validate_target(self) -> "AIGamifyApplyRequest":
        has_type = self.target_type is not None
        has_id = self.target_id is not None
        if has_type != has_id:
            raise ValueError("target_type and target_id must be provided together")
        if self.target_id is not None and int(self.target_id) < 1:
            raise ValueError("target_id must be >= 1")
        return self


class AIGamifyApplyResponse(BaseModel):
    job_id: int
    status: AIGamifyJobStatus = AIGamifyJobStatus.APPLIED
    updated_entity: dict[str, int | str]

    model_config = ConfigDict(from_attributes=True)
