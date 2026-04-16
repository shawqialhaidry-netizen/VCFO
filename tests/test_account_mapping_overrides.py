import pandas as pd

from app.models.company import Company
from app.models.account_mapping_override import AccountMappingOverride
from app.services.account_classifier import (
    build_classification_summary,
    classify_account,
    classify_dataframe_for_company,
)


def test_rule_and_fallback_classification_sources():
    rule_result = classify_account("4010", "Sales Revenue")
    assert rule_result.mapped_type == "revenue"
    assert rule_result.classification_source == "rule"

    fallback_result = classify_account("", "")
    assert fallback_result.mapped_type == "other"
    assert fallback_result.classification_source == "fallback"


def test_company_override_takes_priority_over_rules_and_is_company_scoped(db_session):
    company_a = Company(name="Company A", currency="USD")
    company_b = Company(name="Company B", currency="USD")
    db_session.add_all([company_a, company_b])
    db_session.flush()

    db_session.add_all([
        AccountMappingOverride(
            company_id=company_a.id,
            account_code="4010",
            account_name_hint="Sales Revenue",
            mapped_type="expenses",
            reason="Company A treats this account as an expense override",
        ),
        AccountMappingOverride(
            company_id=company_b.id,
            account_code="4010",
            account_name_hint="Sales Revenue",
            mapped_type="revenue",
            reason="Company B keeps the default classification",
        ),
    ])
    db_session.commit()

    df = pd.DataFrame([
        {
            "account_code": "4010",
            "account_name": "Sales Revenue",
            "debit": 0.0,
            "credit": 100.0,
        }
    ])

    classified_a = classify_dataframe_for_company(df, company_a.id, db_session)
    row_a = classified_a.iloc[0].to_dict()
    assert row_a["mapped_type"] == "expenses"
    assert row_a["classification_source"] == "override"
    assert row_a["match_reason"] == "company_override_code"
    assert row_a["confidence"] == 1.0

    classified_b = classify_dataframe_for_company(df, company_b.id, db_session)
    row_b = classified_b.iloc[0].to_dict()
    assert row_b["mapped_type"] == "revenue"
    assert row_b["classification_source"] == "override"

    company_c = Company(name="Company C", currency="USD")
    db_session.add(company_c)
    db_session.commit()

    classified_without_override = classify_dataframe_for_company(df, company_c.id, db_session)
    row_c = classified_without_override.iloc[0].to_dict()
    assert row_c["mapped_type"] == "revenue"
    assert row_c["classification_source"] == "rule"


def test_company_override_name_fallback_applies_when_code_does_not_match(db_session):
    company = Company(name="Company Name Fallback", currency="USD")
    db_session.add(company)
    db_session.flush()

    db_session.add(
        AccountMappingOverride(
            company_id=company.id,
            account_code="7777",
            account_name_hint="  Deferred   Tax  ",
            mapped_type="tax",
            reason="Name fallback override",
        )
    )
    db_session.commit()

    df = pd.DataFrame([
        {
            "account_code": "8888",
            "account_name": "deferred tax",
            "debit": 15.0,
            "credit": 0.0,
        }
    ])

    classified = classify_dataframe_for_company(df, company.id, db_session)
    row = classified.iloc[0].to_dict()
    assert row["mapped_type"] == "tax"
    assert row["classification_source"] == "override"
    assert row["match_reason"] == "company_override_name"
    assert row["confidence"] == 1.0


def test_company_override_code_match_beats_name_match(db_session):
    company = Company(name="Company Code Priority", currency="USD")
    db_session.add(company)
    db_session.flush()

    db_session.add_all([
        AccountMappingOverride(
            company_id=company.id,
            account_code="0100",
            account_name_hint="cash reserve",
            mapped_type="liabilities",
            reason="Code-specific override should win",
        ),
        AccountMappingOverride(
            company_id=company.id,
            account_code="9999",
            account_name_hint="cash reserve",
            mapped_type="expenses",
            reason="Name fallback should lose to code match",
        ),
    ])
    db_session.commit()

    df = pd.DataFrame([
        {
            "account_code": "0 1 0 0",
            "account_name": "Cash Reserve",
            "debit": 20.0,
            "credit": 0.0,
        }
    ])

    classified = classify_dataframe_for_company(df, company.id, db_session)
    row = classified.iloc[0].to_dict()
    assert row["mapped_type"] == "liabilities"
    assert row["classification_source"] == "override"
    assert row["match_reason"] == "company_override_code"


def test_classification_summary_surfaces_qa_buckets():
    df = pd.DataFrame([
        {
            "account_code": "4010",
            "account_name": "Sales Revenue",
            "mapped_type": "revenue",
            "confidence": 1.0,
            "match_reason": "company_override_code",
            "classification_source": "override",
            "debit": 0.0,
            "credit": 100.0,
        },
        {
            "account_code": "6010",
            "account_name": "Marketing",
            "mapped_type": "expenses",
            "confidence": 0.4,
            "match_reason": "name_keyword (weak) (expenses)",
            "classification_source": "rule",
            "debit": 25.0,
            "credit": 0.0,
        },
        {
            "account_code": "9999",
            "account_name": "Mystery Account",
            "mapped_type": "other",
            "confidence": 0.0,
            "match_reason": "no_match",
            "classification_source": "fallback",
            "debit": 10.0,
            "credit": 0.0,
        },
    ])

    summary = build_classification_summary(df)

    assert summary["classification_source_breakdown"] == {
        "override": {"count": 1},
        "rule": {"count": 1},
        "fallback": {"count": 1},
    }
    assert len(summary["override_accounts"]) == 1
    assert len(summary["rule_accounts"]) == 1
    assert len(summary["fallback_accounts"]) == 1
    assert len(summary["low_confidence_accounts"]) == 1
    assert summary["low_confidence_accounts"][0]["account_code"] == "6010"
    assert len(summary["review_accounts"]) == 2
    assert {row["account_code"] for row in summary["review_accounts"]} == {"6010", "9999"}
    assert summary["qa_summary"] == {
        "low_confidence_threshold": 0.75,
        "override_count": 1,
        "rule_count": 1,
        "fallback_count": 1,
        "low_confidence_count": 1,
        "review_count": 2,
    }
