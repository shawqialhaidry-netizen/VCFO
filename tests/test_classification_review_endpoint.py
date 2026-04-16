from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from app.models.account_mapping_override import AccountMappingOverride
from app.models.trial_balance import TrialBalanceUpload

_TEST_REVIEW_DIR = Path("data/test_classification_review")
_TEST_REVIEW_DIR.mkdir(parents=True, exist_ok=True)


def _write_classified_csv(filename: str, rows: list[dict]) -> Path:
    path = _TEST_REVIEW_DIR / filename
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _seed_review_upload(
    db,
    company_id: str,
    normalized_path: Path,
    *,
    uploaded_at: datetime,
    branch_id: str | None = None,
    period: str = "2026-01",
) -> TrialBalanceUpload:
    rec = TrialBalanceUpload(
        id=str(uuid.uuid4()),
        company_id=company_id,
        original_filename=normalized_path.name,
        raw_path=str(normalized_path),
        normalized_path=str(normalized_path),
        period=period,
        format_detected="monthly/standard",
        record_count=3,
        total_debit=35.0,
        total_credit=100.0,
        is_balanced="true",
        status="ok",
        tb_type="pre_closing",
        branch_id=branch_id,
        uploaded_at=uploaded_at,
    )
    db.add(rec)
    db.commit()
    return rec


def test_classification_review_returns_stable_payload_for_latest_upload(
    client, company_and_headers, db_session
):
    company, headers = company_and_headers

    older_csv = _write_classified_csv(
        "older_review.csv",
        [
            {
                "account_code": "4010",
                "account_name": "Sales Revenue",
                "mapped_type": "revenue",
                "confidence": 0.95,
                "match_reason": "code_prefix+name_keyword (revenue)",
                "classification_source": "rule",
                "debit": 0.0,
                "credit": 100.0,
            }
        ],
    )
    latest_csv = _write_classified_csv(
        "latest_review.csv",
        [
            {
                "account_code": "4010",
                "account_name": "Sales Revenue",
                "mapped_type": "expenses",
                "confidence": 0.75,
                "match_reason": "stale_snapshot_wrong",
                "classification_source": "rule",
                "debit": 0.0,
                "credit": 100.0,
            },
            {
                "account_code": "MKT",
                "account_name": "Marketing",
                "mapped_type": "expenses",
                "confidence": 0.4,
                "match_reason": "name_keyword (weak) (expenses)",
                "classification_source": "rule",
                "debit": 25.0,
                "credit": 0.0,
            },
            {
                "account_code": "ZZZ",
                "account_name": "Mystery Account",
                "mapped_type": "other",
                "confidence": 0.0,
                "match_reason": "no_match",
                "classification_source": "fallback",
                "debit": 10.0,
                "credit": 0.0,
            },
        ],
    )

    now = datetime.utcnow()
    db_session.add(
        AccountMappingOverride(
            company_id=company["id"],
            account_code="4010",
            account_name_hint="Sales Revenue",
            mapped_type="revenue",
            reason="current review truth",
        )
    )
    db_session.commit()
    _seed_review_upload(
        db_session,
        company["id"],
        older_csv,
        uploaded_at=now - timedelta(days=1),
        period="2026-01",
    )
    latest = _seed_review_upload(
        db_session,
        company["id"],
        latest_csv,
        uploaded_at=now,
        period="2026-02",
    )

    r = client.get(f"/api/v1/companies/{company['id']}/classification-review", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["company_id"] == company["id"]
    assert body["upload"]["upload_id"] == latest.id
    assert body["upload"]["period"] == "2026-02"
    assert set(body.keys()) == {
        "company_id",
        "upload",
        "summary_counts",
        "classification_source_breakdown",
        "accounts_needing_review",
        "fallback_accounts",
        "low_confidence_accounts",
        "override_accounts",
        "rule_accounts",
    }
    assert body["summary_counts"] == {
        "classified_ratio": 0.6667,
        "override_count": 1,
        "rule_count": 1,
        "fallback_count": 1,
        "low_confidence_count": 1,
        "review_count": 2,
        "low_confidence_threshold": 0.75,
    }
    assert body["classification_source_breakdown"] == {
        "override": {"count": 1},
        "rule": {"count": 1},
        "fallback": {"count": 1},
    }
    assert {row["account_code"] for row in body["accounts_needing_review"]} == {"MKT", "ZZZ"}
    assert [row["account_code"] for row in body["fallback_accounts"]] == ["ZZZ"]
    assert [row["account_code"] for row in body["low_confidence_accounts"]] == ["MKT"]
    assert [row["account_code"] for row in body["override_accounts"]] == ["4010"]
    assert [row["account_code"] for row in body["rule_accounts"]] == ["MKT"]


def test_classification_review_supports_explicit_upload_id(
    client, company_and_headers, db_session
):
    company, headers = company_and_headers

    csv_a = _write_classified_csv(
        "review_a.csv",
        [
            {
                "account_code": "1111",
                "account_name": "A",
                "mapped_type": "other",
                "confidence": 0.0,
                "match_reason": "no_match",
                "classification_source": "fallback",
                "debit": 5.0,
                "credit": 0.0,
            }
        ],
    )
    csv_b = _write_classified_csv(
        "review_b.csv",
        [
            {
                "account_code": "2222",
                "account_name": "B",
                "mapped_type": "revenue",
                "confidence": 0.95,
                "match_reason": "code_prefix_only (revenue)",
                "classification_source": "rule",
                "debit": 0.0,
                "credit": 50.0,
            }
        ],
    )

    now = datetime.utcnow()
    chosen = _seed_review_upload(db_session, company["id"], csv_a, uploaded_at=now - timedelta(days=1))
    _seed_review_upload(db_session, company["id"], csv_b, uploaded_at=now)

    r = client.get(
        f"/api/v1/companies/{company['id']}/classification-review",
        headers=headers,
        params={"upload_id": chosen.id},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["upload"]["upload_id"] == chosen.id
    assert [row["account_code"] for row in body["rule_accounts"]] == ["1111"]
