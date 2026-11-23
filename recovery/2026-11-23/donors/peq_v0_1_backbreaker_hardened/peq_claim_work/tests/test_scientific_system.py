from __future__ import annotations

from peq.system import PEQSystem
from peq.scientific_claims import ClaimEvidence, ScientificClaim


def test_system_exposes_multisource_claim_assessment():
    system = PEQSystem()
    claim = ScientificClaim(
        claim_id="system-c1",
        proposition="Transparent, collaborative communication can be useful in trauma-related distress.",
        evidence=(
            ClaimEvidence("va_dod_ptsd_2023", "support", 1.0, .9, "group-a"),
            ClaimEvidence("samhsa_trauma_informed", "replication", 1.0, .9, "group-b"),
        ),
    )
    result = system.assess_scientific_claim_set(claim, actionable=True)
    assert result.claim_id == "system-c1"
    assert result.independent_support_groups >= 2
    assert result.support_strength > 0
