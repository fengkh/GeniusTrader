"""create_external_sources_and_announcement_ingestion

Revision ID: 202607230005
Revises: 202607230004
Create Date: 2026-07-24 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "202607230005"
down_revision: str | None = "202607230004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


SOURCE_CATEGORY_VALUES = (
    "'exchange_announcement', 'company_disclosure', 'government_policy', "
    "'government_notice', 'regulator_release', 'regulator_enforcement', "
    "'central_bank_release', 'statistics_release', 'international_official', "
    "'multilateral_organization', 'licensed_financial_media', 'public_financial_media', "
    "'company_news', 'rss', 'public_web', 'user_submitted', 'social_media', 'unknown'"
)

AUTHORITY_LEVEL_VALUES = (
    "'exchange', 'company', 'central_government', 'ministry', 'national_regulator', "
    "'provincial_government', 'provincial_department', 'municipal_government', "
    "'municipal_department', 'international_regulator', 'central_bank', "
    "'multilateral_organization', 'licensed_media', 'public_media', 'user', "
    "'social', 'unknown'"
)

PROVIDER_HEALTH_VALUES = (
    "'unknown', 'pass', 'partial', 'data_insufficient', 'not_available', "
    "'network_error', 'timeout', 'rate_limited', 'access_denied', 'source_changed', "
    "'parse_error', 'content_unavailable', 'legal_hold', 'disabled'"
)


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_information_contents_information_contents_origin_allowed"),
        "information_contents",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_information_contents_information_contents_origin_allowed"),
        "information_contents",
        "content_origin IN ('user_input', 'fetched_page', 'user_correction', 'provider_document')",
    )

    op.create_table(
        "external_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_code", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("publisher_name", sa.String(length=200), nullable=False),
        sa.Column("source_category", sa.String(length=64), nullable=False),
        sa.Column("authority_level", sa.String(length=64), nullable=False),
        sa.Column("source_tier", sa.String(length=16), nullable=False),
        sa.Column("jurisdiction", sa.String(length=120), nullable=True),
        sa.Column("country_code", sa.String(length=8), nullable=True),
        sa.Column("region_code", sa.String(length=32), nullable=True),
        sa.Column("city_code", sa.String(length=32), nullable=True),
        sa.Column("official_domain", sa.String(length=200), nullable=True),
        sa.Column("access_mode", sa.String(length=40), nullable=False),
        sa.Column("content_language", sa.String(length=16), nullable=False),
        sa.Column("provider_adapter", sa.String(length=80), nullable=True),
        sa.Column("authorization_status", sa.String(length=40), nullable=False),
        sa.Column("redistribution_status", sa.String(length=40), nullable=False),
        sa.Column("commercial_use_status", sa.String(length=40), nullable=False),
        sa.Column("legal_review_status", sa.String(length=40), nullable=False),
        sa.Column("health_status", sa.String(length=40), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("experimental", sa.Boolean(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            f"source_category IN ({SOURCE_CATEGORY_VALUES})",
            name=op.f("ck_external_sources_external_sources_category_allowed"),
        ),
        sa.CheckConstraint(
            f"authority_level IN ({AUTHORITY_LEVEL_VALUES})",
            name=op.f("ck_external_sources_external_sources_authority_allowed"),
        ),
        sa.CheckConstraint(
            "source_tier IN ('s', 'a', 'b', 'c', 'd', 'unknown')",
            name=op.f("ck_external_sources_external_sources_tier_allowed"),
        ),
        sa.CheckConstraint(
            "access_mode IN ('official_api', 'public_endpoint', 'rss', 'public_html', "
            "'licensed_api', 'manual_url', 'manual_text', 'unavailable')",
            name=op.f("ck_external_sources_external_sources_access_mode_allowed"),
        ),
        sa.CheckConstraint(
            "authorization_status IN ('testing_only', 'unclear', 'review_required', 'approved', 'prohibited')",
            name=op.f("ck_external_sources_external_sources_authorization_allowed"),
        ),
        sa.CheckConstraint(
            "redistribution_status IN ('unclear', 'metadata_only', 'excerpt_allowed', "
            "'full_text_allowed', 'prohibited')",
            name=op.f("ck_external_sources_external_sources_redistribution_allowed"),
        ),
        sa.CheckConstraint(
            "commercial_use_status IN ('unclear', 'review_required', 'approved', 'prohibited')",
            name=op.f("ck_external_sources_external_sources_commercial_use_allowed"),
        ),
        sa.CheckConstraint(
            "legal_review_status IN ('not_started', 'pending', 'reviewed', 'blocked')",
            name=op.f("ck_external_sources_external_sources_legal_review_allowed"),
        ),
        sa.CheckConstraint(
            f"health_status IN ({PROVIDER_HEALTH_VALUES})",
            name=op.f("ck_external_sources_external_sources_health_allowed"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_external_sources")),
    )
    op.create_index("ix_external_sources_category", "external_sources", ["source_category"])
    op.create_index("ix_external_sources_enabled", "external_sources", ["enabled", "experimental"])
    op.create_index("uq_external_sources_source_code", "external_sources", ["source_code"], unique=True)

    op.create_table(
        "provider_sync_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_source_id", sa.Uuid(), nullable=False),
        sa.Column("capability", sa.String(length=80), nullable=False),
        sa.Column("triggered_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("requested_symbols", sa.JSON(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("created_record_count", sa.Integer(), nullable=False),
        sa.Column("updated_record_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_record_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_summary", sa.String(length=500), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("provider_metadata", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('running', 'complete', 'partial', 'failed', 'data_insufficient', "
            "'not_available', 'network_error', 'timeout', 'rate_limited', 'access_denied', "
            "'source_changed', 'parse_error', 'content_unavailable', 'legal_hold', 'disabled')",
            name=op.f("ck_provider_sync_runs_provider_sync_runs_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["external_source_id"],
            ["external_sources.id"],
            name=op.f("fk_provider_sync_runs_external_source_id_external_sources"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["triggered_by_user_id"],
            ["users.id"],
            name=op.f("fk_provider_sync_runs_triggered_by_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provider_sync_runs")),
    )
    op.create_index("ix_provider_sync_runs_source_capability", "provider_sync_runs", ["external_source_id", "capability"])
    op.create_index("ix_provider_sync_runs_user_started", "provider_sync_runs", ["triggered_by_user_id", "started_at"])

    op.create_table(
        "provider_sync_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_source_id", sa.Uuid(), nullable=False),
        sa.Column("capability", sa.String(length=80), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("scope_type", sa.String(length=40), nullable=False),
        sa.Column("scope_key", sa.String(length=160), nullable=False),
        sa.Column("cursor_type", sa.String(length=80), nullable=True),
        sa.Column("cursor_value", sa.Text(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_item_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_provider_item_id", sa.String(length=120), nullable=True),
        sa.Column("overlap_window_seconds", sa.Integer(), nullable=False),
        sa.Column("health_status", sa.String(length=40), nullable=False),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint(
            f"health_status IN ({PROVIDER_HEALTH_VALUES})",
            name=op.f("ck_provider_sync_states_provider_sync_states_health_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["external_source_id"],
            ["external_sources.id"],
            name=op.f("fk_provider_sync_states_external_source_id_external_sources"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_provider_sync_states_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provider_sync_states")),
    )
    op.create_index(
        "uq_provider_sync_states_scope",
        "provider_sync_states",
        ["external_source_id", "capability", "user_id", "scope_type", "scope_key"],
        unique=True,
    )

    op.create_table(
        "announcement_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_source_id", sa.Uuid(), nullable=False),
        sa.Column("source_code", sa.String(length=80), nullable=False),
        sa.Column("provider_announcement_id", sa.String(length=160), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("normalized_title", sa.String(length=500), nullable=False),
        sa.Column("announcement_type", sa.String(length=80), nullable=False),
        sa.Column("announcement_type_confidence", sa.Float(), nullable=False),
        sa.Column("announcement_type_basis", sa.JSON(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("company_name", sa.String(length=200), nullable=True),
        sa.Column("stock_symbols", sa.JSON(), nullable=False),
        sa.Column("exchange", sa.String(length=16), nullable=True),
        sa.Column("source_page_url", sa.Text(), nullable=False),
        sa.Column("document_url", sa.Text(), nullable=True),
        sa.Column("attachment_urls", sa.JSON(), nullable=False),
        sa.Column("is_pdf", sa.Boolean(), nullable=False),
        sa.Column("is_correction", sa.Boolean(), nullable=False),
        sa.Column("corrected_announcement_id", sa.String(length=160), nullable=True),
        sa.Column("raw_metadata_hash", sa.String(length=64), nullable=False),
        sa.Column("deduplication_key", sa.String(length=64), nullable=False),
        sa.Column("data_completeness", sa.String(length=32), nullable=False),
        sa.Column("missing_fields", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint(
            "data_completeness IN ('complete', 'usable', 'partial', 'insufficient')",
            name=op.f("ck_announcement_records_announcement_records_completeness_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["external_source_id"],
            ["external_sources.id"],
            name=op.f("fk_announcement_records_external_source_id_external_sources"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_announcement_records")),
    )
    op.create_index("ix_announcement_records_deduplication_key", "announcement_records", ["deduplication_key"])
    op.create_index("ix_announcement_records_source_published", "announcement_records", ["external_source_id", "published_at"])
    op.create_index("ix_announcement_records_type", "announcement_records", ["announcement_type"])
    op.create_index(
        "uq_announcement_records_provider_id",
        "announcement_records",
        ["external_source_id", "provider_announcement_id"],
        unique=True,
    )

    op.create_table(
        "user_announcement_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("announcement_record_id", sa.Uuid(), nullable=False),
        sa.Column("sync_run_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("match_type", sa.String(length=40), nullable=False),
        sa.Column("matched_stock_id", sa.Uuid(), nullable=True),
        sa.Column("matched_watchlist_item_id", sa.Uuid(), nullable=True),
        sa.Column("match_evidence", sa.JSON(), nullable=False),
        sa.Column("document_extract_status", sa.String(length=40), nullable=False),
        sa.Column("document_extracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("document_page_count", sa.Integer(), nullable=True),
        sa.Column("document_character_count", sa.Integer(), nullable=True),
        sa.Column("document_limitations", sa.JSON(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint(
            "status IN ('pending', 'reviewed', 'dismissed', 'imported', 'unavailable')",
            name=op.f("ck_user_announcement_candidates_user_announcement_candidates_status_allowed"),
        ),
        sa.CheckConstraint(
            "match_type IN ('exact_symbol', 'provider_metadata', 'exact_company_name', "
            "'ambiguous_name', 'unmatched')",
            name=op.f("ck_user_announcement_candidates_user_announcement_candidates_match_type_allowed"),
        ),
        sa.CheckConstraint(
            "document_extract_status IN ('not_requested', 'succeeded', 'failed', 'unavailable', "
            "'too_large', 'too_many_pages', 'text_unavailable')",
            name=op.f("ck_user_announcement_candidates_user_announcement_candidates_document_extract_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["announcement_record_id"],
            ["announcement_records.id"],
            name=op.f("fk_user_announcement_candidates_announcement_record_id_announcement_records"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["matched_stock_id"],
            ["stocks.id"],
            name=op.f("fk_user_announcement_candidates_matched_stock_id_stocks"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["matched_watchlist_item_id"],
            ["user_watchlist_items.id"],
            name=op.f("fk_user_announcement_candidates_matched_watchlist_item_id_user_watchlist_items"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["sync_run_id"],
            ["provider_sync_runs.id"],
            name=op.f("fk_user_announcement_candidates_sync_run_id_provider_sync_runs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_announcement_candidates_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_announcement_candidates")),
    )
    op.create_index("ix_user_announcement_candidates_stock", "user_announcement_candidates", ["matched_stock_id"])
    op.create_index(
        "ix_user_announcement_candidates_user_status",
        "user_announcement_candidates",
        ["user_id", "status", "created_at"],
    )
    op.create_index(
        "uq_user_announcement_candidates_user_record",
        "user_announcement_candidates",
        ["user_id", "announcement_record_id"],
        unique=True,
    )

    op.create_table(
        "information_ingestion_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("information_item_id", sa.Uuid(), nullable=False),
        sa.Column("external_source_id", sa.Uuid(), nullable=False),
        sa.Column("source_record_type", sa.String(length=40), nullable=False),
        sa.Column("announcement_record_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("import_mode", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_record_type IN ('announcement')",
            name=op.f("ck_information_ingestion_links_information_ingestion_links_record_type_allowed"),
        ),
        sa.CheckConstraint(
            "import_mode IN ('metadata_only', 'extracted_document', 'user_supplemented')",
            name=op.f("ck_information_ingestion_links_information_ingestion_links_import_mode_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["announcement_record_id"],
            ["announcement_records.id"],
            name=op.f("fk_information_ingestion_links_announcement_record_id_announcement_records"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["user_announcement_candidates.id"],
            name=op.f("fk_information_ingestion_links_candidate_id_user_announcement_candidates"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["external_source_id"],
            ["external_sources.id"],
            name=op.f("fk_information_ingestion_links_external_source_id_external_sources"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["information_item_id"],
            ["information_items.id"],
            name=op.f("fk_information_ingestion_links_information_item_id_information_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_information_ingestion_links_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_information_ingestion_links")),
    )
    op.create_index("ix_information_ingestion_links_information", "information_ingestion_links", ["information_item_id"])
    op.create_index("ix_information_ingestion_links_record", "information_ingestion_links", ["announcement_record_id"])
    op.create_index(
        "uq_information_ingestion_links_user_candidate",
        "information_ingestion_links",
        ["user_id", "candidate_id"],
        unique=True,
    )

    op.execute(
        sa.text(
            """
            INSERT INTO external_sources (
                id, source_code, display_name, publisher_name, source_category,
                authority_level, source_tier, jurisdiction, country_code, region_code,
                city_code, official_domain, access_mode, content_language,
                provider_adapter, authorization_status, redistribution_status,
                commercial_use_status, legal_review_status, health_status, enabled,
                experimental, limitations, created_at, updated_at
            )
            VALUES
            (
                '00000000-0000-0000-0000-000000000101',
                'CNINFO',
                '巨潮资讯公告',
                '巨潮资讯网',
                'exchange_announcement',
                'exchange',
                's',
                'CN',
                'CN',
                NULL,
                NULL,
                'cninfo.com.cn',
                'public_endpoint',
                'zh-CN',
                'cninfo',
                'review_required',
                'unclear',
                'unclear',
                'pending',
                'unknown',
                false,
                true,
                '["实验性技术候选；授权、完整性、及时性和稳定性尚未最终确认。"]'::json,
                now(),
                now()
            ),
            (
                '00000000-0000-0000-0000-000000000102',
                'SSE_DISCLOSURE',
                '上交所上市公司公告',
                '上海证券交易所',
                'exchange_announcement',
                'exchange',
                's',
                'CN',
                'CN',
                'SH',
                NULL,
                'sse.com.cn',
                'public_endpoint',
                'zh-CN',
                'sse',
                'review_required',
                'unclear',
                'unclear',
                'pending',
                'unknown',
                false,
                true,
                '["实验性有限备选；小样本能力有限，授权、覆盖和稳定性尚未最终确认。"]'::json,
                now(),
                now()
            )
            ON CONFLICT (source_code) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                publisher_name = EXCLUDED.publisher_name,
                source_category = EXCLUDED.source_category,
                authority_level = EXCLUDED.authority_level,
                source_tier = EXCLUDED.source_tier,
                jurisdiction = EXCLUDED.jurisdiction,
                country_code = EXCLUDED.country_code,
                region_code = EXCLUDED.region_code,
                official_domain = EXCLUDED.official_domain,
                access_mode = EXCLUDED.access_mode,
                content_language = EXCLUDED.content_language,
                provider_adapter = EXCLUDED.provider_adapter,
                authorization_status = EXCLUDED.authorization_status,
                redistribution_status = EXCLUDED.redistribution_status,
                commercial_use_status = EXCLUDED.commercial_use_status,
                legal_review_status = EXCLUDED.legal_review_status,
                experimental = EXCLUDED.experimental,
                limitations = EXCLUDED.limitations,
                updated_at = now()
            """
        )
    )


def downgrade() -> None:
    op.drop_index("uq_information_ingestion_links_user_candidate", table_name="information_ingestion_links")
    op.drop_index("ix_information_ingestion_links_record", table_name="information_ingestion_links")
    op.drop_index("ix_information_ingestion_links_information", table_name="information_ingestion_links")
    op.drop_table("information_ingestion_links")
    op.drop_index("uq_user_announcement_candidates_user_record", table_name="user_announcement_candidates")
    op.drop_index("ix_user_announcement_candidates_user_status", table_name="user_announcement_candidates")
    op.drop_index("ix_user_announcement_candidates_stock", table_name="user_announcement_candidates")
    op.drop_table("user_announcement_candidates")
    op.drop_index("uq_announcement_records_provider_id", table_name="announcement_records")
    op.drop_index("ix_announcement_records_type", table_name="announcement_records")
    op.drop_index("ix_announcement_records_source_published", table_name="announcement_records")
    op.drop_index("ix_announcement_records_deduplication_key", table_name="announcement_records")
    op.drop_table("announcement_records")
    op.drop_index("uq_provider_sync_states_scope", table_name="provider_sync_states")
    op.drop_table("provider_sync_states")
    op.drop_index("ix_provider_sync_runs_user_started", table_name="provider_sync_runs")
    op.drop_index("ix_provider_sync_runs_source_capability", table_name="provider_sync_runs")
    op.drop_table("provider_sync_runs")
    op.drop_index("uq_external_sources_source_code", table_name="external_sources")
    op.drop_index("ix_external_sources_enabled", table_name="external_sources")
    op.drop_index("ix_external_sources_category", table_name="external_sources")
    op.drop_table("external_sources")

    op.drop_constraint(
        op.f("ck_information_contents_information_contents_origin_allowed"),
        "information_contents",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_information_contents_information_contents_origin_allowed"),
        "information_contents",
        "content_origin IN ('user_input', 'fetched_page', 'user_correction')",
    )
