from __future__ import annotations

import core.atena_env_bootstrap as bootstrap


def test_bootstrap_main_when_all_installed(monkeypatch, capsys) -> None:
    monkeypatch.setattr(bootstrap, "is_installed", lambda _pkg: True)

    rc = bootstrap.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "já estão instaladas" in out
