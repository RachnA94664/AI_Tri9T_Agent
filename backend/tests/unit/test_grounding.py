import pytest

from app.agents.grounding import find_ids, ungrounded_ids


def test_find_ids_finds_all_three_kinds():
    text = "REQ-001 has TC-002 and risk RISK-003."
    assert find_ids(text) == {"REQ-001", "TC-002", "RISK-003"}


@pytest.mark.parametrize("text", ["REQ-0011", "XREQ-001", "REQ-1", "req-001", "REQ001", ""])
def test_things_that_are_not_ids_are_ignored(text):
    assert find_ids(text) == set()


def test_ids_that_appear_in_the_evidence_are_grounded():
    evidence = ['{"tool_result": {"ok": true, "result": {"id": "REQ-001"}}}']
    assert ungrounded_ids("REQ-001 is verified.", evidence) == set()


def test_an_id_missing_from_the_evidence_is_flagged():
    evidence = ['{"result": {"id": "REQ-001"}}']
    assert ungrounded_ids("See REQ-001 and REQ-050.", evidence) == {"REQ-050"}


def test_evidence_from_several_tool_results_is_combined():
    evidence = ['{"id": "REQ-001"}', '{"id": "TC-007"}']
    assert ungrounded_ids("REQ-001 and TC-007", evidence) == set()


def test_no_ids_in_the_answer_means_nothing_to_flag():
    assert ungrounded_ids("There are none.", []) == set()
