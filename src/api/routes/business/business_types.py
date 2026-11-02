from src.utils.exceptions import APIError, DatabaseError

"""
Business Types API Routes for Valuation Engine

RESTful API endpoints for business types and categories in the valuation engine.
Provides integration with the database service and maintains compatibility with existing systems.

@author UpSwitch CTO Team
@version 1.0.0
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import structlog

from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from src.services.business_intelligence.integration.business_type_database_service import (
    get_business_type_database_service,
    BusinessTypeDatabaseService
)
from src.services.business_intelligence.integration_engine_db import (
    get_business_type_integration_engine,
    BusinessTypeIntegrationEngine
)
from src.database.business_types_repository import (
    BusinessTypeMetadata,
    BusinessTypeBenchmark,
)
from datetime import datetime

# ============================================================================
# ROUTER SETUP
# ============================================================================

router = APIRouter(prefix="/business-types", tags=["business-types"])
logger = structlog.get_logger(__name__)

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class BusinessTypeResponse(BaseModel):
    """Business type response model"""
    id: str
    title: str
    description: str
    short_description: Optional[str] = None
    icon: str
    category: str              # Primary field (matches frontend)
    category_id: str           # Also available
    industryMapping: str        # camelCase
    keywords: List[str] = Field(default_factory=list)
    popular: bool = False
    # Optional valuation fields in camelCase
    dcfPreference: Optional[Decimal] = None
    multiplesPreference: Optional[Decimal] = None
    ownerDependencyImpact: Optional[Decimal] = None
    keyMetrics: Optional[Dict[str, Any]] = None
    typicalEmployeeRange: Optional[Dict[str, Any]] = None
    typicalRevenueRange: Optional[Dict[str, Any]] = None
    status: str = "active"
    createdAt: str
    updatedAt: str

class BusinessCategoryResponse(BaseModel):
    """Business category response model"""
    id: str
    name: str
    description: Optional[str] = None
    icon: str
    display_order: int
    parent_category_id: Optional[str] = None
    is_active: bool = True

class BusinessTypeSearchResponse(BaseModel):
    """Business type search response model"""
    business_types: List[BusinessTypeResponse]
    total: int
    has_more: bool

class BusinessTypeAnalysisResponse(BaseModel):
    """Business type analysis response model"""
    business_type_id: str
    category: str
    industry: str
    dcf_preference: Decimal
    multiples_preference: Decimal
    owner_dependency_impact: Decimal
    key_metrics: List[str]
    methodology_selection: Dict[str, Any]
    confidence_score: Decimal
    recommendations: List[str]

class ApiResponse(BaseModel):
    """Standard API response model"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    cached: Optional[bool] = None
    timestamp: str

# ============================================================================
# TRANSFORMATION FUNCTIONS
# ============================================================================

def transform_business_type(db_type: BusinessTypeMetadata) -> dict:
    """Transform database business type to frontend-compatible format"""
    return {
        "id": db_type.id,
        "title": db_type.title,
        "description": db_type.description,
        "short_description": db_type.short_description,
        "icon": db_type.icon,
        "category": db_type.category_id,        # Map category_id to category
        "category_id": db_type.category_id,     # Also include category_id
        "industryMapping": db_type.industry_mapping,  # camelCase
        "keywords": db_type.keywords,
        "popular": db_type.popular,
        # Optional valuation fields in camelCase
        "dcfPreference": db_type.dcf_preference,
        "multiplesPreference": db_type.multiples_preference,
        "ownerDependencyImpact": db_type.owner_dependency_impact,
        "keyMetrics": db_type.key_metrics,
        "typicalEmployeeRange": db_type.typical_employee_range,
        "typicalRevenueRange": db_type.typical_revenue_range,
        "status": db_type.status,
        "createdAt": db_type.created_at.isoformat(),
        "updatedAt": db_type.updated_at.isoformat()
    }

def transform_business_category(db_category: Any) -> dict:
    """Transform database business category to frontend-compatible format"""
    return {
        "id": db_category.id,
        "name": db_category.name,
        "description": db_category.description,
        "icon": db_category.icon,
        "display_order": db_category.display_order,
        "parent_category_id": db_category.parent_category_id,
        "is_active": db_category.is_active,
        "created_at": db_category.created_at.isoformat(),
        "updated_at": db_category.updated_at.isoformat()
    }

# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================

async def get_database_service() -> BusinessTypeDatabaseService:
    """Get database service dependency"""
    return get_business_type_database_service()

async def get_integration_engine() -> BusinessTypeIntegrationEngine:
    """Get integration engine dependency"""
    return get_business_type_integration_engine()

# ============================================================================
# BUSINESS CATEGORIES ENDPOINTS
# ============================================================================

@router.get("/categories", response_model=ApiResponse)
async def get_business_categories(
    service: BusinessTypeDatabaseService = Depends(get_database_service)
):
    """Get all business categories"""
    try:
        categories = await service.get_business_categories()

        return ApiResponse(
            success=True,
            data=[BusinessCategoryResponse(**(cat.model_dump() if hasattr(cat, 'model_dump') else cat.dict())) for cat in categories],
            cached=False,
            timestamp=datetime.now().isoformat()
        )
    except DatabaseError as e:
        logger.error(f"Failed to get business categories: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve business categories")

@router.get("/categories/{category_id}", response_model=ApiResponse)
async def get_business_category_by_id(
    category_id: str,
    service: BusinessTypeDatabaseService = Depends(get_database_service)
):
    """Get business category by ID"""
    try:
        category = await service.get_business_category_by_id(category_id)

        if not category:
            raise HTTPException(status_code=404, detail="Category not found")

        return ApiResponse(
            success=True,
            data=BusinessCategoryResponse(**(category.model_dump() if hasattr(category, 'model_dump') else category.dict())),
            cached=False,
            timestamp=datetime.now().isoformat()
        )
    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error(f"Failed to get business category {category_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve business category")

# ============================================================================
# BUSINESS TYPES ENDPOINTS
# ============================================================================

@router.get("/types", response_model=ApiResponse)
async def get_business_types(
    category_id: Optional[str] = Query(None, description="Filter by category ID"),
    popular: Optional[bool] = Query(None, description="Filter by popular status"),
    status: str = Query("active", description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    service: BusinessTypeDatabaseService = Depends(get_database_service)
):
    """Get business types with optional filtering"""
    try:
        # TODO: BusinessTypeSearchParams needs to be implemented in business_types_repository
        # from src.database.business_types_repository import BusinessTypeSearchParams

        search_params = {
            'category_id': category_id,
            'popular': popular,
            'status': status,
            'limit': limit,
            'offset': offset
        }

        result = await service.repository.get_business_types(search_params)

        return ApiResponse(
            success=True,
            data={
                "business_types": [transform_business_type(bt) for bt in result.business_types],
                "total": result.total,
                "has_more": result.has_more
            },
            cached=False,
            timestamp=datetime.now().isoformat()
        )
    except DatabaseError as e:
        logger.error(f"Failed to get business types: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve business types")

@router.get("/types/{business_type_id}", response_model=ApiResponse)
async def get_business_type_by_id(
    business_type_id: str,
    service: BusinessTypeDatabaseService = Depends(get_database_service)
):
    """Get business type by ID"""
    try:
        business_type = await service.repository.get_business_type_by_id(business_type_id)

        if not business_type:
            raise HTTPException(status_code=404, detail="Business type not found")

        return ApiResponse(
            success=True,
            data=transform_business_type(business_type),
            cached=False,
            timestamp=datetime.now().isoformat()
        )
    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error(f"Failed to get business type {business_type_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve business type")

@router.get("/types/search", response_model=ApiResponse)
async def search_business_types(
    q: str = Query(..., description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Number of results to return"),
    service: BusinessTypeDatabaseService = Depends(get_database_service)
):
    """Search business types with full-text search"""
    try:
        business_types = await service.repository.search_business_types(q, limit)

        return ApiResponse(
            success=True,
            data=[transform_business_type(bt) for bt in business_types],
            cached=False,
            timestamp=datetime.now().isoformat()
        )
    except DatabaseError as e:
        logger.error(f"Failed to search business types: {e}")
        raise HTTPException(status_code=500, detail="Failed to search business types")

@router.get("/types/popular", response_model=ApiResponse)
async def get_popular_business_types(
    limit: int = Query(20, ge=1, le=100, description="Number of results to return"),
    service: BusinessTypeDatabaseService = Depends(get_database_service)
):
    """Get popular business types"""
    try:
        business_types = await service.repository.get_popular_business_types(limit)

        return ApiResponse(
            success=True,
            data=[transform_business_type(bt) for bt in business_types],
            cached=False,
            timestamp=datetime.now().isoformat()
        )
    except APIError as e:
        logger.error(f"Failed to get popular business types: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve popular business types")

# ============================================================================
# BUSINESS TYPE INTELLIGENCE ENDPOINTS
# ============================================================================

@router.post("/analyze", response_model=ApiResponse)
async def analyze_business_type(
    business_type_id: str,
    business_characteristics: Dict[str, Any],
    engine: BusinessTypeIntegrationEngine = Depends(get_integration_engine)
):
    """Analyze a business type and provide methodology recommendations"""
    try:
        analysis = await engine.analyze_business_type(business_type_id, business_characteristics)

        if not analysis:
            raise HTTPException(status_code=404, detail="Business type not found or analysis failed")

        return ApiResponse(
            success=True,
            data=BusinessTypeAnalysisResponse(
                business_type_id=analysis.business_type_id,
                category=analysis.category,
                industry=analysis.industry,
                dcf_preference=analysis.dcf_preference,
                multiples_preference=analysis.multiples_preference,
                owner_dependency_impact=analysis.owner_dependency_impact,
                key_metrics=analysis.key_metrics,
                methodology_selection={
                    "dcf_weight": analysis.methodology_selection.dcf_weight,
                    "multiples_weight": analysis.methodology_selection.multiples_weight,
                    "confidence_score": analysis.methodology_selection.confidence_score,
                    "business_characteristics_impact": analysis.methodology_selection.business_characteristics_impact,
                    "owner_dependency_impact": analysis.methodology_selection.owner_dependency_impact,
                    "market_context_impact": analysis.methodology_selection.market_context_impact
                },
                confidence_score=analysis.confidence_score,
                recommendations=analysis.recommendations
            ),
            cached=False,
            timestamp=datetime.now().isoformat()
        )
    except HTTPException:
        raise
    except APIError as e:
        logger.error(f"Failed to analyze business type {business_type_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze business type")

@router.get("/intelligence/{business_type_id}", response_model=ApiResponse)
async def get_business_type_intelligence(
    business_type_id: str,
    engine: BusinessTypeIntegrationEngine = Depends(get_integration_engine)
):
    """Get comprehensive business type intelligence"""
    try:
        intelligence = await engine.get_business_type_intelligence(business_type_id)

        if not intelligence:
            raise HTTPException(status_code=404, detail="Business type not found")

        return ApiResponse(
            success=True,
            data=intelligence,
            cached=False,
            timestamp=datetime.now().isoformat()
        )
    except HTTPException:
        raise
    except DatabaseError as e:
        logger.error(f"Failed to get business type intelligence for {business_type_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve business type intelligence")

# ============================================================================
# HEALTH AND ADMIN ENDPOINTS
# ============================================================================

@router.get("/health", response_model=ApiResponse)
async def get_health_status(
    service: BusinessTypeDatabaseService = Depends(get_database_service),
    engine: BusinessTypeIntegrationEngine = Depends(get_integration_engine)
):
    """Get business types service health status"""
    try:
        db_health = await service.get_health_status()
        engine_health = await engine.get_health_status()

        return ApiResponse(
            success=True,
            data={
                "database_service": db_health,
                "integration_engine": engine_health
            },
            cached=False,
            timestamp=datetime.now().isoformat()
        )
    except DatabaseError as e:
        logger.error(f"Failed to get health status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get health status")

@router.post("/refresh", response_model=ApiResponse)
async def refresh_business_types_data(
    engine: BusinessTypeIntegrationEngine = Depends(get_integration_engine)
):
    """Refresh business types data from database"""
    try:
        await engine.refresh_data()

        return ApiResponse(
            success=True,
            data={"message": "Business types data refreshed successfully"},
            cached=False,
            timestamp=datetime.now().isoformat()
        )
    except DatabaseError as e:
        logger.error(f"Failed to refresh business types data: {e}")
        raise HTTPException(status_code=500, detail="Failed to refresh business types data")

# ============================================================================
# ERROR HANDLING
# ============================================================================
# Note: Exception handlers are handled by the main FastAPI app, not individual routers

# Note: Exception handlers are handled by the main FastAPI app, not individual routers
