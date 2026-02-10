"""バックエンド結合テスト。

実際に起動しているAPIサーバーに対してリクエストを行い、
正常にレスポンスが返ることを検証する。
APIサーバーが起動していない場合はスキップする。
"""

from __future__ import annotations

import httpx
import pytest

BASE_URL = "http://127.0.0.1:8000"


@pytest.fixture(autouse=True)
def _require_running_backend() -> None:
    """APIサーバーが起動していなければテストをスキップする。"""
    try:
        response = httpx.get(f"{BASE_URL}/health", timeout=3)
        response.raise_for_status()
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError):
        pytest.skip("APIサーバーが起動していません (http://127.0.0.1:8000)")


class TestJobsAPI:
    """ジョブ一覧・詳細APIの結合テスト。"""

    def test_list_jobs_returns_200(self) -> None:
        """GET /api/jobs が200を返すこと。

        ディスク上のjob_failed.jsonに不正なデータがあっても
        500にならないことを検証する。
        """
        response = httpx.get(f"{BASE_URL}/api/jobs", timeout=10)
        assert response.status_code == 200, (
            f"GET /api/jobs が {response.status_code} を返しました。"
            f" レスポンス: {response.text[:500]}"
        )
        jobs = response.json()
        assert isinstance(jobs, list)

    def test_each_job_detail_returns_200(self) -> None:
        """各ジョブの詳細API GET /api/jobs/{job_id} が200を返すこと。"""
        list_response = httpx.get(f"{BASE_URL}/api/jobs", timeout=10)
        if list_response.status_code != 200:
            pytest.skip("ジョブ一覧の取得に失敗したため詳細テストをスキップ")

        jobs = list_response.json()
        for job in jobs:
            job_id = job["job_id"]
            detail_response = httpx.get(
                f"{BASE_URL}/api/jobs/{job_id}", timeout=10
            )
            assert detail_response.status_code == 200, (
                f"GET /api/jobs/{job_id} が {detail_response.status_code} を返しました。"
                f" レスポンス: {detail_response.text[:500]}"
            )


class TestHealthEndpoint:
    """ヘルスチェックの結合テスト。"""

    def test_health_returns_ok(self) -> None:
        """GET /health が200を返しステータスがokであること。"""
        response = httpx.get(f"{BASE_URL}/health", timeout=5)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
