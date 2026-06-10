from rag_agents import quality_guard, supervisor, synthesis


def test_supervisor_routes_refund_to_refund_source():
    state = {"question": "Sản phẩm license key có được hoàn tiền không?", "workers_called": [], "events": []}
    result = supervisor.run(state)
    assert result["domain_filters"] == ["policy_refund_v4"]


def test_capabilities_intent_skips_document_rag():
    state = {
        "question": "Bạn có thể giải đáp những gì cho tôi?",
        "workers_called": [],
        "events": [],
        "errors": [],
        "risk_high": False,
    }
    state = supervisor.run(state)
    assert state["intent"] == "capabilities"
    assert state["domain_filters"] == []
    state = synthesis.run(state)
    assert "5 nhóm tài liệu" in state["answer"]
    assert state["citations"] == []
    assert state["synthesis_provider"] == "system_capabilities"


def test_quality_guard_rejects_stale_refund():
    state = {
        "evidence": [{"doc_id": "policy_refund_v4", "text": "Hoàn tiền trong 14 ngày làm việc."}],
        "workers_called": [],
        "events": [],
    }
    result = quality_guard.run(state)
    assert result["evidence"] == []
    assert len(result["rejected_evidence"]) == 1


def test_synthesis_abstains_without_evidence():
    state = {
        "question": "Thông tin không có",
        "evidence": [],
        "rejected_evidence": [],
        "risk_high": False,
        "workers_called": [],
        "events": [],
    }
    result = synthesis.run(state)
    assert result["confidence"] == 0.0
    assert result["needs_human_review"] is True
