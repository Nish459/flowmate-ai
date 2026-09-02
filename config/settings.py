"""Central configuration for FlowMate, loaded from environment / .env.

Every other module (data generation, BigQuery loading, and later the
agents/API) should import `settings` from here rather than reading
os.environ directly, so there is a single source of truth for config.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gcp_project_id: str = Field(..., alias="GCP_PROJECT_ID")
    gcp_location: str = Field("us-central1", alias="GCP_LOCATION")

    bq_dataset: str = Field("flowmate", alias="BQ_DATASET")
    bq_tickets_table: str = Field("tickets", alias="BQ_TICKETS_TABLE")
    bq_pr_reviews_table: str = Field("pr_reviews", alias="BQ_PR_REVIEWS_TABLE")
    bq_team_velocity_table: str = Field("team_velocity", alias="BQ_TEAM_VELOCITY_TABLE")

    firestore_standups_collection: str = Field("standups", alias="FIRESTORE_STANDUPS_COLLECTION")
    firestore_scans_collection: str = Field("scans", alias="FIRESTORE_SCANS_COLLECTION")
    firestore_panels_collection: str = Field("panels", alias="FIRESTORE_PANELS_COLLECTION")

    cors_allowed_origins: str = Field(
        "http://localhost:5173", alias="CORS_ALLOWED_ORIGINS"
    )

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    gemini_api_key: str = Field("", alias="GEMINI_API_KEY")
    gemini_model: str = Field("gemini-3.6-flash", alias="GEMINI_MODEL")

    @property
    def bq_tickets_table_id(self) -> str:
        return f"{self.gcp_project_id}.{self.bq_dataset}.{self.bq_tickets_table}"

    @property
    def bq_pr_reviews_table_id(self) -> str:
        return f"{self.gcp_project_id}.{self.bq_dataset}.{self.bq_pr_reviews_table}"

    @property
    def bq_team_velocity_table_id(self) -> str:
        return f"{self.gcp_project_id}.{self.bq_dataset}.{self.bq_team_velocity_table}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
