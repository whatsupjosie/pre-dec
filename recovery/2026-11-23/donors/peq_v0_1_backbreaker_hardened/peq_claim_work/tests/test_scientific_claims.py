from __future__ import annotations

from peq.scientific_claims import ClaimEvidence, ScientificClaim, assess_scientific_claim, assess_scientific_claim_set
from peq.clinical_evidence import SOURCES, all_scientific_sources, SourceRecord

ALL_SOURCES = {row["source_id"]: SourceRecord(**row) for row in all_scientific_sources()}


def test_source_quality_is_assessed_without_promotion():
    result = assess_scientific_claim(SOURCES['nimh_ptsd'], proposition='This source describes trauma-related symptoms.')
    assert result.status == 'reference_only'
    assert result.operational_readiness == 0.0
    assert result.evidence_quality > 0


def test_actionable_claim_remains_provisional():
    result = assess_scientific_claim(
        SOURCES['va_dod_ptsd_2023'],
        proposition='This guidance supports a cautious, transparent interaction approach.',
        actionable=True,
    )
    assert result.status == 'provisional_actionable'
    assert result.operational_readiness > 0


def test_high_stakes_claims_are_not_operationalized():
    result = assess_scientific_claim(
        SOURCES['va_dod_ptsd_2023'],
        proposition='Do this intervention in all cases.',
        actionable=True,
        dangerous_if_wrong=True,
    )
    assert result.status == 'reference_only_high_stakes'
    assert result.operational_readiness == 0.0
    assert result.warnings


def test_independent_replication_is_visible():
    claim = ScientificClaim(
        claim_id='c1',
        proposition='A cautious transparent interaction approach is useful for trauma-related distress.',
        evidence=(
            ClaimEvidence('va_dod_ptsd_2023', 'support', effect=1, quality=.9, independent_group='guideline-a', peer_reviewed=False),
            ClaimEvidence('samhsa_trauma_informed', 'replication', effect=1, quality=.9, independent_group='framework-b', peer_reviewed=False),
            ClaimEvidence('va_ptsd_triggers', 'replication', effect=1, quality=.8, independent_group='education-c', peer_reviewed=False),
        ),
    )
    result = assess_scientific_claim_set(claim, ALL_SOURCES, actionable=True)
    assert result.independent_support_groups >= 2
    assert result.replication_strength > 0
    assert result.status == 'independently_supported'


def test_credible_dissent_is_retained_and_reduces_readiness():
    claim = ScientificClaim(
        claim_id='c2',
        proposition='This measurement is a definitive indicator.',
        evidence=(
            ClaimEvidence('caps5_meta', 'support', effect=1, quality=.95, independent_group='meta-a', peer_reviewed=True),
            ClaimEvidence('panss_cosmin', 'dissent', effect=-.8, quality=.90, independent_group='review-b', peer_reviewed=True),
        ),
    )
    result = assess_scientific_claim_set(claim, ALL_SOURCES, actionable=True)
    assert result.dissent_strength > 0
    assert result.contradiction_strength > 0
    assert any('dissent' in w.lower() for w in result.warnings)
    assert result.status in {'provisionally_contested', 'supported_with_limitations'}


def test_same_independence_group_does_not_count_as_multiple_replications():
    claim = ScientificClaim(
        claim_id='c3',
        proposition='X is useful.',
        evidence=(
            ClaimEvidence('caps5_meta', 'support', effect=1, quality=.9, independent_group='same', peer_reviewed=True),
            ClaimEvidence('pcl5_psychometrics', 'replication', effect=1, quality=.9, independent_group='same', peer_reviewed=True),
        ),
    )
    result = assess_scientific_claim_set(claim, ALL_SOURCES, actionable=True)
    assert result.independent_support_groups == 1
    assert result.status != 'independently_supported'


def test_null_evidence_is_not_treated_as_dissent_but_reduces_support():
    claim = ScientificClaim(
        claim_id='c4',
        proposition='X works.',
        evidence=(
            ClaimEvidence('va_dod_ptsd_2023', 'support', effect=1, quality=.8, independent_group='a'),
            ClaimEvidence('psychosis_prevention', 'null', effect=0.6, quality=.8, independent_group='b', peer_reviewed=True),
        ),
    )
    result = assess_scientific_claim_set(claim, ALL_SOURCES, actionable=True)
    assert result.contradiction_strength > 0
    assert result.dissent_strength == 0


def test_duplicate_source_is_not_counted_twice():
    claim = ScientificClaim(
        claim_id='c5',
        proposition='X is useful.',
        evidence=(
            ClaimEvidence('va_dod_ptsd_2023', 'support', effect=1, quality=.9, independent_group='same'),
            ClaimEvidence('va_dod_ptsd_2023', 'replication', effect=1, quality=.9, independent_group='other'),
        ),
    )
    result = assess_scientific_claim_set(claim, ALL_SOURCES, actionable=True)
    assert result.evidence_count == 1
    assert any('duplicate source ignored' in row for row in result.evidence_summary)


def test_unknown_source_is_not_silently_used_as_evidence():
    claim = ScientificClaim(
        claim_id='c6',
        proposition='X is useful.',
        evidence=(ClaimEvidence('not-in-registry', 'support', effect=1, quality=.9, independent_group='x'),),
    )
    result = assess_scientific_claim_set(claim, ALL_SOURCES, actionable=True)
    assert result.support_strength == 0
    assert result.independent_support_groups == 0
    assert any('unresolved source' in row for row in result.evidence_summary)
