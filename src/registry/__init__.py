"""
Registry-First Architecture

This module implements the registry-first approach for business valuations.
Instead of asking users to upload documents, we fetch public financial data
from official company registries first, then ask for current year data only.

Belgian KBO boundary:
- Titan owns KBO ingestion, schema, indexes, search, and refreshes.
- ValuationIQ uses Titan's registry API and does not connect to a KBO database.

Supported Registries:
- Belgium: KBO/BCE (Titan API)
- Netherlands: KVK (commercial API via Overheid.io / Company.info)
- UK: Companies House (planned)
- Germany: Bundesanzeiger (planned)
- France: Infogreffe (planned)
- Luxembourg: RCS (planned)
"""

from .base import RegistryClient, RegistrySearchResult, RegistryFinancialData
from .netherlands import NetherlandsRegistryClient
from .router import RegistryRouter
from .titan_kbo_client import TitanKBOClient

__all__ = [
    "RegistryClient",
    "RegistrySearchResult", 
    "RegistryFinancialData",
    "NetherlandsRegistryClient",
    "RegistryRouter",
    "TitanKBOClient",
]
