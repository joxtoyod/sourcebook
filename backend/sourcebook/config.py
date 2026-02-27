import os
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    db_path: str = ""
    # Name or full path of the claude CLI binary
    claude_bin: str = "claude"
    # Model passed to --model; defaults to the CLI's own default if left empty
    claude_model: str = "claude-sonnet-4-5"
    project_root: str = ""

    model_config = {"env_file": ".env"}

    @field_validator("db_path", mode="before")
    @classmethod
    def resolve_db_path(cls, v: str) -> str:
        if not v:
            dot_dir = Path(os.getcwd()) / ".sourcebook"
            dot_dir.mkdir(parents=True, exist_ok=True)
            return str(dot_dir / "sourcebook.db")
        return v

    @field_validator("project_root", mode="before")
    @classmethod
    def resolve_project_root(cls, v: str) -> str:
        return v or str(Path(os.getcwd()))

    @property
    def index_path(self) -> Path:
        """Path to the cached condensed project index markdown file."""
        return Path(self.db_path).parent / "project-index.md"


settings = Settings()
