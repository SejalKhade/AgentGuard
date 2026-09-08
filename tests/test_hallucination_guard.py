"""AgentGuard Unit Tests — HallucinationGuard"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.hallucination_guard import (
    extract_numbers,
    get_source_numbers,
    verify_claim,
    evaluate,
)


class TestExtractNumbers:
    def test_pulls_number_and_unit(self):
        found = extract_numbers("Risk score is 100 and latency 25 ms")
        values = {(f["number"], f["unit"]) for f in found}
        assert (100.0, "") in values
        assert (25.0, "ms") in values

    def test_includes_context(self):
        found = extract_numbers("blast radius of 3 means catastrophic")
        assert "catastrophic" in found[0]["context"]


class TestSourceNumbers:
    def test_recurses_dict_and_list(self):
        src = get_source_numbers({"a": 1, "b": {"c": 2}, "d": [3, {"e": 4}]})
        paths = {s["path"]: s["value"] for s in src}
        assert paths == {"a": 1.0, "b.c": 2.0, "d[0]": 3.0, "d[1].e": 4.0}


class TestVerifyClaim:
    SOURCES = [{"value": 100.0, "path": "risk_score"}, {"value": 2.0, "path": "approvers"}]

    def test_verified_within_tolerance(self):
        r = verify_claim(101.0, self.SOURCES)
        assert r["status"] == "VERIFIED"
        assert r["source_path"] == "risk_score"

    def test_approximation_within_15_pct(self):
        r = verify_claim(112.0, self.SOURCES)
        assert r["status"] == "APPROXIMATION"

    def test_unverified_when_absent(self):
        r = verify_claim(9999.0, self.SOURCES)
        assert r["status"] == "UNVERIFIED"
        assert r["matched_value"] is None

    def test_skips_zero_source(self):
        r = verify_claim(5.0, [{"value": 0.0, "path": "zero"}])
        assert r["status"] == "UNVERIFIED"


class TestEvaluate:
    def test_missing_input_short_circuits(self):
        assert evaluate("", {"a": 1})["evaluation_performed"] is False
        assert evaluate("text", {})["evaluation_performed"] is False

    def test_reliable_when_claims_match_source(self):
        pipeline = {"risk_score": 100.0, "blast_radius": 3, "approvers_needed": 2}
        text = "The risk score is 100 with blast radius 3 needing 2 approvers."
        result = evaluate(text, pipeline)
        assert result["evaluation_performed"] is True
        assert result["total_claims"] == 3
        assert result["verified"] == 3
        assert result["overall_status"] == "RELIABLE"
        assert result["reliability_score"] == 100.0

    def test_flags_unverified_numbers(self):
        pipeline = {"risk_score": 100.0}
        result = evaluate("The score is 100 but downtime was 13 hours costing 500.", pipeline)
        assert result["unverified"] >= 1
        assert result["overall_status"] in {"PARTIALLY RELIABLE", "REVIEW REQUIRED"}

    def test_ignores_sub_one_values(self):
        result = evaluate("Confidence 0.5 only", {"risk_score": 100.0})
        assert result["total_claims"] == 0
        assert result["reliability_score"] == 100.0
