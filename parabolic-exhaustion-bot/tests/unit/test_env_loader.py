import os

from parabolic_exhaustion.live.env import load_env_file


def test_load_env_file_reads_key_values(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# comment",
                "OANDA_API_TOKEN=test-token",
                "DISCORD_WEBHOOK_URL_NAS100_PARABOLIC_PAPER=https://example.test/hook",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("OANDA_API_TOKEN", raising=False)

    loaded = load_env_file(env_file)

    assert loaded["OANDA_API_TOKEN"] == "test-token"
    assert os.environ["OANDA_API_TOKEN"] == "test-token"
