from sources.domestic import _weibo_cookie


def test_weibo_cookie_requires_environment_variable(monkeypatch):
    monkeypatch.delenv("WEIBO_COOKIE", raising=False)
    assert _weibo_cookie() == ""


def test_weibo_cookie_reads_and_strips_environment_variable(monkeypatch):
    monkeypatch.setenv("WEIBO_COOKIE", "  SUB=example  ")
    assert _weibo_cookie() == "SUB=example"
