"""
SQLAlchemy Database Models

Defines database tables for storing valuation requests, results, and historical data.
"""

import uuid
from datetime import datetime
from typing import Optional

from src.utils.logging import get_logger
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, JSON, Text, Boolean, Numeric,
    Index, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from src.database.connection import Base

logger = get_logger(__name__)



class Valuation(Base):
    """
    Valuation Request Model

    Stores input data for valuation calculations including company information,
    financial data, and market context.
    """
    __tablename__ = "valuations"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # User/Business Reference
    user_id = Column(String(255), nullable=True, index=True)
    business_id = Column(String(255), nullable=True, index=True)

    # Company Information
    company_name = Column(String(255), nullable=False)
    country_code = Column(String(2), nullable=False, index=True)  # ISO 2-letter code
    industry = Column(String(100), nullable=False, index=True)
    business_model = Column(String(100), nullable=True)
    founding_year = Column(Integer, nullable=True)

    # Business Structure (New fields for ownership)
    business_type = Column(
        SQLEnum('sole-trader', 'company', name='business_type_enum'),
        nullable=False,
        default='company'
    )
    shares_for_sale = Column(Numeric(5, 2), nullable=True)  # Percentage (0-100)
    number_of_employees = Column(Integer, nullable=True)  # Total FTE count
    number_of_owners = Column(Integer, nullable=True, default=1)  # Operational owners

    # Financial Data (Current Year)
    current_year = Column(Integer, nullable=False)
    revenue = Column(Float, nullable=False)
    ebitda = Column(Float, nullable=True)
    net_income = Column(Float, nullable=True)
    total_assets = Column(Float, nullable=True)
    total_debt = Column(Float, nullable=True)
    cash = Column(Float, nullable=True)

    # Additional Financial Metrics (Optional)
    operating_expenses = Column(Float, nullable=True)
    depreciation_amortization = Column(Float, nullable=True)
    interest_expense = Column(Float, nullable=True)
    taxes = Column(Float, nullable=True)
    capex = Column(Float, nullable=True)

    # Historical Data (3 years for CAGR calculation)
    historical_data = Column(JSONB, nullable=True)  # Array of {year, revenue, ebitda}

    # Market Context (Optional)
    market_context = Column(JSONB, nullable=True)
    industry_benchmarks = Column(JSONB, nullable=True)

    # Request Metadata
    request_source = Column(String(50), default='api')  # api, frontend, test
    request_ip = Column(String(50), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    results = relationship("ValuationResult", back_populates="valuation", cascade="all, delete-orphan")

    # Indexes for performance
    __table_args__ = (
        Index('idx_valuation_created', 'created_at'),
        Index('idx_valuation_country_industry', 'country_code', 'industry'),
        Index('idx_valuation_user_business', 'user_id', 'business_id'),
    )

    def __repr__(self):
        return f"<Valuation(id={self.id}, company={self.company_name}, created={self.created_at})>"


class ValuationResult(Base):
    """
    Valuation Result Model

    Stores calculated valuation results including enterprise value, equity value,
    methodology details, and confidence scores.
    """
    __tablename__ = "valuation_results"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign Key to Valuation
    valuation_id = Column(UUID(as_uuid=True), ForeignKey('valuations.id'), nullable=False, index=True)

    # Valuation Results
    enterprise_value_low = Column(Float, nullable=False)
    enterprise_value_mid = Column(Float, nullable=False)
    enterprise_value_high = Column(Float, nullable=False)

    equity_value_low = Column(Float, nullable=False)
    equity_value_mid = Column(Float, nullable=False)
    equity_value_high = Column(Float, nullable=False)

    recommended_asking_price = Column(Float, nullable=False)

    # Ownership Adjustments (New fields)
    ownership_adjustment = Column(JSONB, nullable=True)  # {revenue_cagr, ebitda_cagr, growth_multiplier, etc.}

    # Methodology
    methodology = Column(String(50), nullable=False)  # dcf, multiples, synthesized
    primary_method = Column(String(50), nullable=True)
    confidence = Column(Float, nullable=False)  # 0-100

    # DCF Details
    dcf_result = Column(JSONB, nullable=True)  # Full DCF calculation details

    # Multiples Details
    multiples_result = Column(JSONB, nullable=True)  # Market multiples calculation

    # Financial Metrics
    financial_metrics = Column(JSONB, nullable=True)  # All calculated ratios

    # Value Drivers & Risks
    value_drivers = Column(JSONB, nullable=True)  # Array of strings
    risk_factors = Column(JSONB, nullable=True)  # Array of strings

    # Sensitivity Analysis
    sensitivity_analysis = Column(JSONB, nullable=True)

    # Calculation Metadata
    calculation_time_ms = Column(Integer, nullable=True)  # Time taken for calculation
    engine_version = Column(String(20), default='1.0.0')

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationship
    valuation = relationship("Valuation", back_populates="results")

    # Indexes
    __table_args__ = (
        Index('idx_result_valuation', 'valuation_id'),
        Index('idx_result_created', 'created_at'),
    )

    def __repr__(self):
        return f"<ValuationResult(id={self.id}, valuation_id={self.valuation_id}, equity_mid={self.equity_value_mid})>"


class ValuationCache(Base):
    """
    Valuation Cache Model

    Caches external API data (OECD, ECB, FMP) to reduce API calls and improve performance.
    """
    __tablename__ = "valuation_cache"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Cache Key (unique identifier for cached data)
    cache_key = Column(String(255), unique=True, nullable=False, index=True)

    # Data Source
    source = Column(String(50), nullable=False)  # oecd, ecb, fmp, alpha_vantage
    data_type = Column(String(50), nullable=False)  # gdp, inflation, multiples, rates

    # Cached Data
    data = Column(JSONB, nullable=False)

    # Metadata
    country_code = Column(String(2), nullable=True, index=True)
    industry = Column(String(100), nullable=True, index=True)

    # Cache Management
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    hit_count = Column(Integer, default=0)  # Track cache usage

    # Indexes
    __table_args__ = (
        Index('idx_cache_key', 'cache_key'),
        Index('idx_cache_expires', 'expires_at'),
        Index('idx_cache_source_type', 'source', 'data_type'),
    )

    def __repr__(self):
        return f"<ValuationCache(key={self.cache_key}, source={self.source}, expires={self.expires_at})>"


class AuditLog(Base):
    """
    Audit Log Model

    Tracks all API requests, errors, and system events for security and debugging.
    """
    __tablename__ = "audit_logs"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Event Information
    event_type = Column(String(50), nullable=False, index=True)  # api_request, error, calculation
    event_category = Column(String(50), nullable=False)  # valuation, health, admin

    # User/Request Context
    user_id = Column(String(255), nullable=True, index=True)
    request_ip = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)

    # Event Details
    endpoint = Column(String(255), nullable=True)
    http_method = Column(String(10), nullable=True)
    status_code = Column(Integer, nullable=True)

    # Data
    request_data = Column(JSONB, nullable=True)
    response_data = Column(JSONB, nullable=True)
    error_details = Column(JSONB, nullable=True)

    # Performance
    execution_time_ms = Column(Integer, nullable=True)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Indexes
    __table_args__ = (
        Index('idx_audit_event_type', 'event_type'),
        Index('idx_audit_created', 'created_at'),
        Index('idx_audit_user', 'user_id'),
    )

    def __repr__(self):
        return f"<AuditLog(id={self.id}, event={self.event_type}, time={self.created_at})>"


class IndustryBenchmark(Base):
    """
    Industry Benchmarks Model

    Stores industry-specific financial benchmarks and multiples for valuation analysis.
    This table provides real market data to improve business type intelligence.
    """
    __tablename__ = "industry_benchmarks"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Industry Classification
    industry = Column(String(100), nullable=False, index=True)
    country_code = Column(String(2), nullable=False, index=True)

    # Financial Multiples
    median_ev_revenue = Column(Float, nullable=True)
    median_ev_ebitda = Column(Float, nullable=True)
    median_pe = Column(Float, nullable=True)
    median_pb = Column(Float, nullable=True)
    median_ps = Column(Float, nullable=True)

    # Growth Metrics
    median_revenue_growth = Column(Float, nullable=True)
    median_ebitda_growth = Column(Float, nullable=True)
    median_earnings_growth = Column(Float, nullable=True)

    # Profitability Metrics
    median_ebitda_margin = Column(Float, nullable=True)
    median_net_margin = Column(Float, nullable=True)
    median_roe = Column(Float, nullable=True)
    median_roa = Column(Float, nullable=True)

    # Risk Metrics
    median_beta = Column(Float, nullable=True)
    median_debt_to_equity = Column(Float, nullable=True)
    median_current_ratio = Column(Float, nullable=True)

    # Data Quality Metrics
    data_quality = Column(Float, default=0.7, nullable=False)
    sample_size = Column(Integer, default=0, nullable=False)
    confidence_score = Column(Float, default=0.5, nullable=False)

    # Metadata
    data_source = Column(String(100), default='upswitch_historical', nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Indexes for performance
    __table_args__ = (
        Index('idx_industry_benchmarks_industry_country', 'industry', 'country_code'),
        Index('idx_industry_benchmarks_last_updated', 'last_updated'),
        Index('idx_industry_benchmarks_data_quality', 'data_quality'),
    )

    def __repr__(self):
        return f"<IndustryBenchmark(industry={self.industry}, country={self.country_code}, data_quality={self.data_quality})>"


class FAQEntry(Base):
    """
    FAQ Entry Model
    
    Stores frequently asked questions with answers for conversational Q&A during
    valuation data collection.
    
    Features:
    - Multi-language support (en, nl, fr)
    - Frequency tracking for optimization
    - Category organization
    - Cross-reference to terminology glossary
    """
    __tablename__ = "faq_entries"
    
    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Question and Answer
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    
    # Classification
    category = Column(String(50), nullable=False, index=True)  # financial, legal, tax, etc.
    language = Column(String(5), nullable=False, default='en', index=True)  # en, nl, fr
    
    # Tracking
    frequency_count = Column(Integer, nullable=False, default=0)  # How many times asked
    last_asked = Column(DateTime, nullable=True)  # When last asked
    
    # Cross-reference
    related_term = Column(String(100), nullable=True)  # Related glossary term
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_faq_category_language', 'category', 'language'),
        Index('idx_faq_frequency', 'frequency_count'),
        Index('idx_faq_last_asked', 'last_asked'),
    )
    
    def __repr__(self):
        return f"<FAQEntry(id={self.id}, question='{self.question[:50]}...', language={self.language})>"


class TruthEntry(Base):
    """
    Truth Entry Model
    
    Canonical knowledge base for Q&A validation. Stores expert-verified facts
    that serve as ground truth for fact-checking AI-generated answers.
    
    Features:
    - Expert approval workflow with provenance tracking
    - Temporal validity with expiry dates for regulations
    - Version control with semantic versioning
    - Multi-language support (en, nl, fr)
    - Full-text search on keywords
    - Audit trail of all changes
    
    Used by ValidationPipeline for fact-checking gate.
    """
    __tablename__ = "truth_entries"
    
    # Primary Key (semantic versioning)
    id = Column(String(100), primary_key=True)  # e.g., "EBITDA_DEFINITION_v1.0.0"
    
    # Classification
    category = Column(String(50), nullable=False, index=True)  # financial_metrics, tax_regulation, etc.
    claim_type = Column(String(30), nullable=False)  # definition, formula, range, regulation
    
    # The Canonical Truth
    canonical_statement = Column(Text, nullable=False)
    formula = Column(Text, nullable=True)
    valid_range_min = Column(Float, nullable=True)
    valid_range_max = Column(Float, nullable=True)
    
    # Provenance & Trust
    source = Column(Text, nullable=False)  # "Big 4 Audit Firm", "IRS Publication"
    source_url = Column(Text, nullable=True)
    expert_id = Column(String(50), nullable=False)
    expert_notes = Column(Text, nullable=True)
    
    # Temporal Validity
    approved_date = Column(DateTime, nullable=False)
    last_reviewed = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=True, index=True)  # For tax/legal facts
    
    # Discovery & Matching (PostgreSQL array type)
    keywords = Column(JSON, nullable=False)  # Store as JSON for SQLite/PostgreSQL compatibility
    related_claims = Column(JSON, nullable=True)
    
    # Multi-language
    language = Column(String(5), nullable=False, default='en', index=True)
    
    # Version Control
    version = Column(String(20), nullable=False, default='1.0.0')
    changelog = Column(JSONB, nullable=True)
    
    # Status
    status = Column(String(20), nullable=False, default='active', index=True)
    superseded_by = Column(String(100), nullable=True)
    
    # Audit Trail
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(String(50), nullable=False)
    updated_by = Column(String(50), nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_truth_category', 'category'),
        Index('idx_truth_category_language', 'category', 'language'),
        Index('idx_truth_expires', 'expires_at'),
    )
    
    def __repr__(self):
        return f"<TruthEntry(id={self.id}, category={self.category}, language={self.language})>"


class ValidationReport(Base):
    """
    Validation Report Model
    
    Audit trail of Q&A validation attempts through the 5-gate validation pipeline.
    Tracks every answer validation for compliance, quality monitoring, and cost analysis.
    
    Features:
    - Complete gate-by-gate results with evidence
    - Confidence scoring (0-100)
    - Risk assessment (low/medium/high)
    - Performance metrics (duration, cost)
    - Full audit trail for SOC2 compliance
    """
    __tablename__ = "validation_reports"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Answer Being Validated
    answer_id = Column(String(100), nullable=False, index=True)  # Hash of question+answer
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    source = Column(String(20), nullable=False, index=True)  # glossary, faq, ai
    
    # Validation Results
    overall_result = Column(String(20), nullable=False, index=True)  # pass, fail, warning
    confidence_score = Column(Float, nullable=False)  # 0.00-100.00
    risk_level = Column(String(20), nullable=False)  # low, medium, high
    
    # Gate Results (JSONB for flexibility)
    gate_results = Column(JSONB, nullable=False)  # Array of {gate, result, confidence, evidence}
    
    # Metadata
    question_domain = Column(String(50), nullable=True)
    question_language = Column(String(5), nullable=True)
    validation_duration_ms = Column(Integer, nullable=True)
    
    # Decision Outcomes
    approved_for_delivery = Column(Boolean, nullable=False, index=True)
    requires_human_review = Column(Boolean, nullable=False, index=True)
    disclaimer_required = Column(Boolean, nullable=False)
    disclaimer_text = Column(Text, nullable=True)
    
    # Audit Trail
    validated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    validator_version = Column(String(20), default='1.0.0')
    
    # Indexes
    __table_args__ = (
        Index('idx_validation_answer_id', 'answer_id'),
        Index('idx_validation_source', 'source'),
        Index('idx_validation_date', 'validated_at'),
    )
    
    def __repr__(self):
        return f"<ValidationReport(id={self.id}, result={self.overall_result}, confidence={self.confidence_score:.1f})>"


class ReviewQueue(Base):
    """
    Review Queue Model
    
    Human expert review workflow for Q&A answers that fail automated validation.
    Implements priority-based assignment with SLA tracking and escalation.
    
    Features:
    - Priority-based routing (urgent/high/normal/low)
    - Expert assignment and workload balancing
    - SLA tracking with automatic breach detection
    - Approval workflow with corrected answers
    - Integration with truth database (create entries from reviews)
    """
    __tablename__ = "review_queue"
    
    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Reference to Validation Report
    validation_report_id = Column(UUID(as_uuid=True), ForeignKey('validation_reports.id'), nullable=True)
    
    # Question & Answer
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    
    # Review Assignment
    priority = Column(String(20), nullable=False, default='normal', index=True)  # urgent, high, normal, low
    assigned_to = Column(String(50), nullable=True, index=True)  # Expert ID
    status = Column(String(20), nullable=False, default='pending', index=True)  # pending, in_review, approved, rejected
    
    # Expert Review
    expert_decision = Column(String(20), nullable=True)  # approve, reject, revise
    expert_notes = Column(Text, nullable=True)
    corrected_answer = Column(Text, nullable=True)
    
    # Workflow Metadata
    failure_reasons = Column(JSONB, nullable=True)
    suggested_truth_entry = Column(JSONB, nullable=True)
    
    # SLA Tracking
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    assigned_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    sla_deadline = Column(DateTime, nullable=True, index=True)
    sla_breached = Column(Boolean, default=False)
    
    # Audit
    created_by = Column(String(50), default='system')
    updated_by = Column(String(50), nullable=True)
    
    # Relationship
    validation_report = relationship("ValidationReport", foreign_keys=[validation_report_id])
    
    # Indexes
    __table_args__ = (
        Index('idx_review_status', 'status'),
        Index('idx_review_priority', 'priority'),
        Index('idx_review_sla_deadline', 'sla_deadline'),
    )
    
    def __repr__(self):
        return f"<ReviewQueue(id={self.id}, priority={self.priority}, status={self.status})>"
