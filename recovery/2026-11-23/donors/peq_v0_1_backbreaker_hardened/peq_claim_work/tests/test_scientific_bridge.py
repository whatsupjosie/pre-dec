from __future__ import annotations

import math
import pytest

from peq.models import EvidenceDomain
from peq.retrieval import PEQEvidenceRetriever
from peq.scientific_bridge import ScientificClaimPromotion, promote_scientific_evidence


def _evidence():
    bundle = PEQEvidenceRetriever().retrieve_for_packet(
        __import__("cre_eq.models", fromlist=["ObservationPacket"]).ObservationPacket(
            subject_id="u1",
            is_primary_user=True,
            text="I am anxious",
            context={"situation": "deadline"},
        ),
        top_k=4,
        alternatives_k=2,
    )
    assert bundle.primary
    return bundle.primary[0]


def test_retrieval_is_not_automatically_promoted():
    ev = _evidence()
    with pytest.raises(ValueError, match="verified claim"):
        promote_scientific_evidence(
            ev,
            proposition="This source supports anxiety in the current person.",
            state_directions={"anxiety": 1.0},
            verified_claim=False,
        )


def test_explicit_promotion_requires_state_directions():
    ev = _evidence()
    with pytest.raises(ValueError, match="state-specific directions"):
        promote_scientific_evidence(
            ev,
            proposition="The literature supports this relationship.",
            state_directions={},
            verified_claim=True,
        )


def test_explicit_promotion_creates_general_knowledge_evidence():
    ev = _evidence()
    contribution = promote_scientific_evidence(
        ev,
        proposition="The verified literature supports a cautious anxiety interpretation under this evidence pattern.",
        state_directions={"anxiety": 0.7, "excitement": -0.2},
        verified_claim=True,
        strength=0.8,
        reliability=0.75,
    )
    assert contribution.domain is EvidenceDomain.GENERAL_KNOWLEDGE
    assert contribution.state_directions["anxiety"] == 0.7
    assert contribution.state_directions["excitement"] == -0.2
    assert contribution.source_id == ev.evidence_id


def test_nonfinite_direction_is_rejected_after_cleaning():
    ev = _evidence()
    with pytest.raises(ValueError, match="No finite"):
        promote_scientific_evidence(
            ev,
            proposition="Verified claim",
            state_directions={"anxiety": float("nan"), "anger": float("inf")},
            verified_claim=True,
        )
