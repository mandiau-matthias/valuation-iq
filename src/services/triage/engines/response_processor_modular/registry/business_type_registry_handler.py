"""
BusinessTypeRegistryHandler

Handles business type validation via Node.js API following KBO pattern.
Supports exact match (auto-select) and fuzzy match (suggestions).
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, List, Optional

import httpx

logger = logging.getLogger(__name__)

API_TIMEOUT_SECONDS = 15
API_BASE_URL = os.getenv("BUSINESS_TYPES_API_URL", "http://localhost:3000/api/business-types")


@dataclass
class BusinessTypeResult:
    id: str
    title: str
    short_description: str = ""
    description: str = ""
    industry: str = ""
    industry_mapping: str = ""
    category_id: str = ""
    icon: str = ""


class BusinessTypeRegistryHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def lookup_business_type(self, query: str, context: Any) -> List[BusinessTypeResult]:
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT_SECONDS) as client:
                response = await asyncio.wait_for(
                    client.get(API_BASE_URL, params={"q": query}),
                    timeout=API_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                data = response.json()

                if not data.get("success", False):
                    return []

                items = data.get("data", [])
                if not items:
                    return []

                return [
                    BusinessTypeResult(
                        id=item.get("id", ""),
                        title=item.get("title", ""),
                        short_description=item.get("shortDescription", ""),
                        description=item.get("description", ""),
                        industry=item.get("industry", ""),
                        industry_mapping=item.get("industryMapping", ""),
                        category_id=item.get("categoryId", ""),
                        icon=item.get("icon", ""),
                    )
                    for item in items
                ]
        except (asyncio.TimeoutError, TimeoutError):
            self.logger.warning("Business type lookup timed out for query=%s", query)
            return []
        except httpx.HTTPStatusError as e:
            self.logger.warning("HTTP error during business type lookup: %s", e)
            return []
        except httpx.RequestError as e:
            self.logger.warning("Request error during business type lookup: %s", e)
            return []
        except Exception as e:
            self.logger.exception("Unexpected error during business type lookup")
            return []

    def process_business_type_results(
        self,
        matching_types: List[Any],
        business_type_text: str,
        context: Any,
    ) -> Optional[str]:
        if not matching_types:
            return None

        if len(matching_types) == 1:
            match = matching_types[0]
            bt_id = getattr(match, "id", "")
            title = getattr(match, "title", "")
            industry = getattr(match, "industry_mapping", "") or getattr(match, "industry", "")

            context.business_type_id = bt_id
            context.business_type_metadata = {
                "title": title,
                "industry": industry,
                "is_exact_match": True,
            }
            context.industry = industry
            context.business_type = title

            try:
                cd = context.collected_data
                if isinstance(cd, dict):
                    cd["business_type"] = title
                    cd["business_type_id"] = bt_id
            except (AttributeError, TypeError):
                pass

            return None

        titles = [getattr(m, "title", "") for m in matching_types]
        context.business_type_suggestions = matching_types

        options = "\n".join(f"  - {t}" for t in titles)
        return f"Did you mean one of these?\n{options}"
