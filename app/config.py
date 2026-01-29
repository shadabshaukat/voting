from pydantic import Field, validator
from pydantic_settings import BaseSettings
from typing import Optional
from urllib.parse import quote_plus

class Settings(BaseSettings):
    # Individual DB components (OCI PostgreSQL requires SSL)
    DB_HOST: str = Field(..., env="DB_HOST")
    DB_PORT: str = Field(..., env="DB_PORT")
    DB_NAME: str = Field(..., env="DB_NAME")
    DB_USER: str = Field(..., env="DB_USER")
    DB_PASSWORD: str = Field(..., env="DB_PASSWORD")

    # Strip surrounding single quotes if the password is quoted in .env
    @validator("DB_PASSWORD", pre=True)
    def _strip_quotes(cls, v: str) -> str:
        if isinstance(v, str) and v.startswith("'") and v.endswith("'"):
            return v[1:-1]
        return v
    DB_SSLMODE: str = Field("require", env="DB_SSLMODE")

    # Simple admin credentials (read from .env)
    ADMIN_USERNAME: str = Field(..., env="ADMIN_USERNAME")
    ADMIN_PASSWORD: str = Field(..., env="ADMIN_PASSWORD")

    # Optional full URL (overrides components if provided)
    DATABASE_URL: Optional[str] = None

    JWT_SECRET_KEY: str = Field("supersecretkey", env="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 1 hour

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def database_url(self) -> str:
        """
        Construct the PostgreSQL connection URL from individual components.
        If DATABASE_URL is explicitly set, it is returned unchanged.
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL

        # URLencode the password to safely handle special characters
        pwd = quote_plus(self.DB_PASSWORD)
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{pwd}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?sslmode={self.DB_SSLMODE}"
        )

settings = Settings()