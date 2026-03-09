from src.utils.privacy import scrub_text


class DummyConfig:
    def __init__(self):
        self.privacy_mode = "shared"
        self.privacy_scrubber = "scrubadub"
        self.privacy_hash_salt = "salt"


def test_scrubber_selection_falls_back_to_builtin():
    config = DummyConfig()
    result = scrub_text(
        "email me at user@example.com",
        mode=config.privacy_mode,
        salt=config.privacy_hash_salt,
        config=config,
    )
    assert "[REDACTED:EMAIL]" in result.text
