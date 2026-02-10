"""ワーカー起動時のバリデーションテスト。

モックではなく実際の設定ロジックを検証し、
環境設定の不備を起動時に検出できることを確認する。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from meetingai_backend.settings import Settings
from meetingai_backend.worker import _validate_settings


def _make_settings(**overrides: object) -> Settings:
    """テスト用のSettingsを作成する。必須フィールドにはデフォルト値を設定。"""
    defaults: dict[str, object] = {
        "upload_root": Path("/tmp/test-uploads"),
        "redis_url": "redis://localhost:6379/0",
        "job_queue_name": "test:jobs",
        "job_timeout_seconds": 60,
        "ffmpeg_path": "ffmpeg",
        "openai_api_key": "sk-test-key",
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


class TestValidateSettings:
    """_validate_settings のテスト。"""

    def test_passes_with_valid_settings(self) -> None:
        """全必須設定がある場合はエラーにならない。"""
        settings = _make_settings(openai_api_key="sk-test-key")
        _validate_settings(settings)  # 例外なし

    def test_fails_without_openai_api_key(self) -> None:
        """OPENAI_API_KEYが未設定の場合、起動時にエラーになる。"""
        settings = _make_settings(openai_api_key=None)
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            _validate_settings(settings)

    def test_fails_with_empty_openai_api_key(self) -> None:
        """OPENAI_API_KEYが空文字の場合もエラーになる。"""
        settings = _make_settings(openai_api_key="")
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            _validate_settings(settings)


class TestWorkerCanStart:
    """ワーカーが実際に起動できることを検証する。"""

    @pytest.fixture()
    def _set_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    @pytest.mark.usefixtures("_set_api_key")
    def test_worker_connects_to_redis_and_starts(self) -> None:
        """Redis に接続してワーカーが起動できることを確認する。

        実際の Redis が必要。利用不可の場合はスキップ。
        """
        from redis import Redis, ConnectionError as RedisConnectionError
        from rq import Queue, Worker

        from meetingai_backend.settings import get_settings

        settings = get_settings()
        try:
            connection = Redis.from_url(settings.redis_url)
            connection.ping()
        except (RedisConnectionError, OSError):
            pytest.skip("Redis is not available")

        queue = Queue(
            "test:startup-check",
            connection=connection,
            default_timeout=10,
        )

        # Worker インスタンスが作れること = 起動可能
        worker = Worker(
            queues=[queue],
            connection=connection,
            name="test-startup-worker",
        )
        assert worker.name == "test-startup-worker"

        # クリーンアップ
        worker.register_death()


class TestSettingsFromEnv:
    """Settings.from_env が環境変数を正しく読むことを検証する。"""

    def test_reads_openai_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """OPENAI_API_KEYが環境変数にあればSettingsに反映される。"""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-from-env")
        settings = Settings.from_env()
        assert settings.openai_api_key == "sk-test-from-env"

    def test_openai_api_key_none_when_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OPENAI_API_KEYが未設定ならNoneになる。"""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        settings = Settings.from_env()
        assert settings.openai_api_key is None
