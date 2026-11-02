from src.utils.exceptions import APIError, DataValidationError

"""
Service Registry

This module handles service registration, discovery, and management
for the Registry API refactoring.
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timezone, timedelta
import logging
from decimal import Decimal
from src.utils.decimal_helpers import to_decimal, from_decimal
from .registry.registry_types import (
    RegistryEndpoint, RegistryStatus, CountryCode, RegistryType,
    CompanySearchResult, CompanyDetails, FinancialData,
    DEFAULT_REGISTRY_ENDPOINTS, COUNTRY_CONFIGURATIONS
)

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """
    Service registry for managing registry endpoints

    Handles:
    - Service registration and discovery
    - Health monitoring
    - Load balancing
    - Failover management
    """

    def __init__(self) -> None:
        """
        Initialize the service registry.
        
        Sets up service tracking, health monitoring, and metrics collection.
        """
        self.logger = logger
        self.registered_services: Dict[str, RegistryEndpoint] = {}
        self.service_health: Dict[str, Dict[str, Any]] = {}
        self.service_metrics: Dict[str, Dict[str, Any]] = {}

        # Initialize default services
        self._initialize_default_services()

        self.logger.info("ServiceRegistry initialized")

    def register_service(self, endpoint: RegistryEndpoint) -> None:
        """
        Register a new service endpoint

        Args:
            endpoint: Registry endpoint to register
        """
        try:
            self.registered_services[endpoint.endpoint_id] = endpoint
            self.service_health[endpoint.endpoint_id] = {
                "status": RegistryStatus.ACTIVE,
                "last_check": datetime.now(timezone.utc),
                "response_time": Decimal('0.0'),
                "error_count": 0,
                "success_count": 0
            }
            self.service_metrics[endpoint.endpoint_id] = {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "average_response_time": Decimal('0.0'),
                "last_request": None
            }

            self.logger.info("Service registered",
                           extra={
                               'endpoint_id': endpoint.endpoint_id,
                               'service_name': endpoint.name,
                               'country': endpoint.country_code.value
                           })

        except APIError as e:
            self.logger.error(f"Service registration failed: {e}")

    def unregister_service(self, endpoint_id: str) -> None:
        """
        Unregister a service endpoint

        Args:
            endpoint_id: ID of the endpoint to unregister
        """
        try:
            if endpoint_id in self.registered_services:
                del self.registered_services[endpoint_id]
                if endpoint_id in self.service_health:
                    del self.service_health[endpoint_id]
                if endpoint_id in self.service_metrics:
                    del self.service_metrics[endpoint_id]

                self.logger.info("Service unregistered", extra={'endpoint_id': endpoint_id})

        except APIError as e:
            self.logger.error(f"Service unregistration failed: {e}")

    def get_service(self, endpoint_id: str) -> Optional[RegistryEndpoint]:
        """
        Get a registered service by ID

        Args:
            endpoint_id: Service endpoint ID

        Returns:
            Registry endpoint or None if not found
        """
        return self.registered_services.get(endpoint_id)

    def get_services_by_country(self, country_code: CountryCode) -> List[RegistryEndpoint]:
        """
        Get all services for a specific country

        Args:
            country_code: Country code to filter by

        Returns:
            List of registry endpoints for the country
        """
        return [
            endpoint for endpoint in self.registered_services.values()
            if endpoint.country_code == country_code
        ]

    def get_active_services(self) -> List[RegistryEndpoint]:
        """Get all active services"""
        return [
            endpoint for endpoint in self.registered_services.values()
            if endpoint.status == RegistryStatus.ACTIVE
        ]

    def get_services_by_type(self, registry_type: RegistryType) -> List[RegistryEndpoint]:
        """
        Get services by registry type

        Args:
            registry_type: Type of registry to filter by

        Returns:
            List of registry endpoints of the specified type
        """
        return [
            endpoint for endpoint in self.registered_services.values()
            if endpoint.registry_type == registry_type
        ]

    def check_service_health(self, endpoint_id: str) -> Dict[str, Any]:
        """
        Check health of a specific service

        Args:
            endpoint_id: Service endpoint ID

        Returns:
            Health check results
        """
        try:
            endpoint = self.get_service(endpoint_id)
            if not endpoint:
                return {"status": "not_found", "error": "Service not found"}

            # Simulate health check (in real implementation, this would make actual requests)
            start_time = datetime.now(timezone.utc)

            # Simulate response time
            import time
            time.sleep(Decimal('0.1'))  # Simulate network delay

            response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            # Update health status
            self.service_health[endpoint_id]["last_check"] = datetime.now(timezone.utc)
            self.service_health[endpoint_id]["response_time"] = response_time

            # Determine health status based on response time
            if response_time < 1000:  # Less than 1 second
                health_status = RegistryStatus.ACTIVE
            elif response_time < 5000:  # Less than 5 seconds
                health_status = RegistryStatus.ACTIVE
            else:
                health_status = RegistryStatus.ERROR

            self.service_health[endpoint_id]["status"] = health_status

            return {
                "status": health_status.value,
                "response_time_ms": response_time,
                "last_check": self.service_health[endpoint_id]["last_check"].isoformat(),
                "endpoint": endpoint.name
            }

        except DataValidationError as e:
            self.logger.error(f"Health check failed for {endpoint_id}: {e}")
            return {"status": "error", "error": str(e)}

    def check_all_services_health(self) -> Dict[str, Any]:
        """Check health of all registered services"""
        try:
            health_results = {}
            active_count = 0
            total_count = len(self.registered_services)

            for endpoint_id in self.registered_services.keys():
                health_result = self.check_service_health(endpoint_id)
                health_results[endpoint_id] = health_result

                if health_result.get("status") == "active":
                    active_count += 1

            return {
                "overall_status": "healthy" if active_count == total_count else "degraded",
                "total_services": total_count,
                "active_services": active_count,
                "service_health": health_results,
                "last_check": datetime.now(timezone.utc).isoformat()
            }

        except DataValidationError as e:
            self.logger.error(f"Health check failed: {e}")
            return {"status": "error", "error": str(e)}

    def update_service_metrics(
        self,
        endpoint_id: str,
        success: bool,
        response_time: Decimal
    ) -> None:
        """
        Update service metrics

        Args:
            endpoint_id: Service endpoint ID
            success: Whether the request was successful
            response_time: Response time in milliseconds
        """
        try:
            if endpoint_id not in self.service_metrics:
                self.service_metrics[endpoint_id] = {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "average_response_time": Decimal('0.0'),
                    "last_request": None
                }

            metrics = self.service_metrics[endpoint_id]
            metrics["total_requests"] += 1

            if success:
                metrics["successful_requests"] += 1
            else:
                metrics["failed_requests"] += 1

            # Update average response time
            total_time = metrics["average_response_time"] * (metrics["total_requests"] - 1)
            metrics["average_response_time"] = (total_time + response_time) / metrics["total_requests"]

            metrics["last_request"] = datetime.now(timezone.utc)

            # Update health status based on success rate
            if metrics["total_requests"] > 0:
                success_rate = metrics["successful_requests"] / metrics["total_requests"]
                if success_rate < 0.5:
                    self.service_health[endpoint_id]["status"] = RegistryStatus.ERROR
                elif success_rate < 0.8:
                    self.service_health[endpoint_id]["status"] = RegistryStatus.MAINTENANCE
                else:
                    self.service_health[endpoint_id]["status"] = RegistryStatus.ACTIVE

        except APIError as e:
            self.logger.error(f"Metrics update failed for {endpoint_id}: {e}")

    def get_service_metrics(self, endpoint_id: str) -> Dict[str, Any]:
        """Get metrics for a specific service"""
        return self.service_metrics.get(endpoint_id, {})

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all services"""
        return self.service_metrics.copy()

    def get_best_service_for_country(self, country_code: CountryCode) -> Optional[RegistryEndpoint]:
        """
        Get the best available service for a country

        Args:
            country_code: Country code

        Returns:
            Best available registry endpoint for the country
        """
        try:
            country_services = self.get_services_by_country(country_code)
            if not country_services:
                return None

            # Filter active services
            active_services = [
                service for service in country_services
                if service.status == RegistryStatus.ACTIVE
            ]

            if not active_services:
                return None

            # Sort by priority and health
            def service_score(service: RegistryEndpoint) -> Decimal:
                """
                Calculate service score for ranking.
                
                Args:
                    service: Registry endpoint to score
                    
                Returns:
                    Service score (higher is better)
                """
                priority_score = Decimal('1.0') / service.priority
                health_score = Decimal('1.0') if self.service_health.get(service.endpoint_id, {}).get("status") == RegistryStatus.ACTIVE else Decimal('0.5')
                return priority_score * health_score

            best_service = max(active_services, key=service_score)

            self.logger.debug("Selected best service for country",
                            country=country_code.value,
                            service=best_service.endpoint_id,
                            priority=best_service.priority)

            return best_service

        except APIError as e:
            self.logger.error(f"Service selection failed for {country_code.value}: {e}")
            return None

    def get_service_status(self) -> Dict[str, Any]:
        """Get overall service registry status"""
        try:
            total_services = len(self.registered_services)
            active_services = len(self.get_active_services())

            return {
                "total_services": total_services,
                "active_services": active_services,
                "inactive_services": total_services - active_services,
                "health_status": "healthy" if active_services == total_services else "degraded",
                "last_updated": datetime.now(timezone.utc).isoformat()
            }

        except APIError as e:
            self.logger.error(f"Status retrieval failed: {e}")
            return {"error": str(e)}

    def _initialize_default_services(self) -> None:
        """
        Initialize default registry services.
        
        Registers all default registry endpoints from DEFAULT_REGISTRY_ENDPOINTS.
        """
        try:
            for endpoint in DEFAULT_REGISTRY_ENDPOINTS.values():
                self.register_service(endpoint)

            self.logger.info("Default services initialized",
                           extra={'service_count': len(DEFAULT_REGISTRY_ENDPOINTS)})

        except APIError as e:
            self.logger.error(f"Default service initialization failed: {e}")

    def get_supported_countries(self) -> List[str]:
        """Get list of supported countries"""
        return list(set(
            endpoint.country_code.value for endpoint in self.registered_services.values()
        ))

    def get_country_configuration(self, country_code: CountryCode) -> Dict[str, Any]:
        """Get configuration for a specific country"""
        return COUNTRY_CONFIGURATIONS.get(country_code, {})

    def is_country_supported(self, country_code: str) -> bool:
        """Check if a country is supported"""
        try:
            country_enum = CountryCode(country_code.upper())
            return country_enum in [endpoint.country_code for endpoint in self.registered_services.values()]
        except ValueError:
            return False

    def get_registry_status(self) -> Dict[str, Any]:
        """Get overall registry status"""
        try:
            total_services = len(self.registered_services)
            active_services = 0

            for service in self.registered_services.values():
                if hasattr(service, 'status') and service.status == "active":
                    active_services += 1
                elif isinstance(service, dict) and service.get("status") == "active":
                    active_services += 1

            return {
                "status": "operational" if active_services > 0 else "degraded",
                "total_services": total_services,
                "active_services": active_services,
                "last_updated": "2024-01-01T00:00:00Z"
            }

        except APIError as e:
            self.logger.error(f"Registry status failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
