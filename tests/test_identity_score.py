from osint_agent.profiling.identity_score import score_pair


def _profile(**kw):
    base = {"key": "github:jdoe", "username": "jdoe", "display_names": ["John Doe"],
            "emails": [], "phones": [], "bios": [], "locations": ["Bangkok"],
            "organizations": [], "interests": ["tech"], "explicit_links": []}
    base.update(kw)
    return base


def test_same_email_is_confirmed():
    result = score_pair(_profile(emails=["a@b.com"]), _profile(key="x:jdoe", emails=["a@b.com"], display_names=[]))
    assert result["verdict"] == "Confirmed"
    assert "same_email" in result["signals"]


def test_username_alone_is_weak():
    result = score_pair(
        {"key": "a", "username": "jdoe", "display_names": [], "emails": [], "phones": [], "bios": [],
         "locations": [], "organizations": [], "interests": [], "explicit_links": []},
        {"key": "b", "username": "jdoe", "display_names": [], "emails": [], "phones": [], "bios": [],
         "locations": [], "organizations": [], "interests": [], "explicit_links": []},
    )
    assert result["verdict"] == "Unverified"


def test_name_and_location_is_probable():
    result = score_pair(_profile(), _profile(key="reddit:jdoe", username="jdoe"))
    assert result["verdict"] in {"Probable", "Possible"}


def test_full_name_alone_is_not_confirmed():
    result = score_pair(_profile(username="a", locations=[]), _profile(key="b", username="b", locations=[]))
    assert result["verdict"] != "Confirmed"
