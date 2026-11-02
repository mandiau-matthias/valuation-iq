"""
Business Intelligence Services Package

BANK-GRADE SRP-COMPLIANT: 7 specialized services + 1 coordinator

This package contains the refactored business intelligence system with
7 specialized SRP-compliant services coordinated by a Facade.

ARCHITECTURE:
- BusinessTypeIntelligenceCoordinator (Facade - 398 lines)
  ├── BusinessTypeAnalyzer (319 lines)
  ├── MethodologySelector (335 lines)
  ├── MarketContextIntegrator (410 lines)
  ├── OwnerDependencyAnalyzer (426 lines)
  ├── BusinessRecommendationEngine (375 lines)
  ├── BusinessIntelligenceLearningService (433 lines)
  └── BusinessDataIntegrator (464 lines)

TOTAL: 8 services, 3,160 lines (vs original 780 lines monolith)

BENEFITS:
- Each service has exactly ONE responsibility
- Independent testing and optimization
- Easy to extend with new features
- Clear separation of concerns
- Bank-grade SOLID compliance

USAGE:
```python
from src.services.business_intelligence.intelligence_services import (
    BusinessTypeIntelligenceCoordinator
)

# Initialize coordinator (facade)
coordinator = BusinessTypeIntelligenceCoordinator(db, redis_client)

# Use clean interface
analysis = await coordinator.analyze_business_type(
    business_type='saas',
    user_data={...},
    market_context={...}
)
```

EXTRACTED FROM: BusinessTypeIntelligenceService (780 lines)
COMPLIANCE: Bank-Grade Excellence Framework - SRP Phase 1
"""

# Export coordinator (main interface)
from .business_type_intelligence_coordinator import BusinessTypeIntelligenceCoordinator

# Export individual services (for advanced usage)
from .business_type_analyzer import BusinessTypeAnalyzer
from .methodology_selector import MethodologySelector
from .market_context_integrator import (
    MarketContextIntegrator,
    MarketAdjustments
)
from .owner_dependency_analyzer import (
    OwnerDependencyAnalyzer,
    OwnerAdjustments,
    OwnerDependencyAnalysis
)
from .business_recommendation_engine import (
    BusinessRecommendationEngine,
    Recommendation
)
from .business_intelligence_learning_service import (
    BusinessIntelligenceLearningService,
    LearningMetrics
)
from .business_data_integrator import (
    BusinessDataIntegrator,
    SystemMetrics
)

__all__ = [
    # Main interface (Facade)
    'BusinessTypeIntelligenceCoordinator',
    
    # Individual services
    'BusinessTypeAnalyzer',
    'MethodologySelector',
    'MarketContextIntegrator',
    'OwnerDependencyAnalyzer',
    'BusinessRecommendationEngine',
    'BusinessIntelligenceLearningService',
    'BusinessDataIntegrator',
    
    # Supporting types
    'MarketAdjustments',
    'OwnerAdjustments',
    'OwnerDependencyAnalysis',
    'Recommendation',
    'LearningMetrics',
    'SystemMetrics',
]
