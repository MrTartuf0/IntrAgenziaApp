from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MENU_USERNAME: str
    MENU_PASSWORD: str
    REDIS_URL: str = "redis://localhost:6379/0"

    class Config:
        env_file = ".env"


settings = Settings()
