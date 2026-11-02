from src.utils.exceptions import DataValidationError, ValuationRangeError

"""
European Central Bank (ECB) API Adapter

Fetches monetary policy and interest rate data from the ECB
- Risk-free rates (government bond yields)
- Policy interest rates
- Bond yields for WACC calculations
- Money market rates

API Documentation: https://sdw.ecb.europa.eu/
"""

from typing import Dict, List, Optional, Any
from datetime import datetime

from src.utils.logging import get_logger

from src.adapters.base_adapter import BaseAdapter, DataNotFoundError, ValidationError
from src.config import get_settings
from decimal import Decimal

logger = get_logger(__name__)
settings = get_settings()


class ECBAdapter(BaseAdapter):
    """
    European Central Bank API adapter

    Provides access to:
    - 10-year government bond yields (risk-free rate)
    - ECB policy rates
    - Money market rates
    - Credit spreads
    """

    # ECB data series keys
    SERIES_GOV_BOND_10Y = "YC"   # Yield curve
    SERIES_POLICY_RATE = "FM"    # Financial Markets
    SERIES_MONEY_MARKET = "MM"   # Money Market

    # Country codes for government bonds
    BOND_COUNTRY_CODES = {
        "DE": "DE",  # Germany (considered risk-free for Euro Area)
        "FR": "FR",  # France
        "GB": "GB",  # United Kingdom
        "UK": "GB",  # Alias used elsewhere in the valuation stack
        "NL": "NL",  # Netherlands
        "ES": "ES",  # Spain
        "IT": "IT",  # Italy
        "BE": "BE",  # Belgium
        "EU": "DE",  # Default to German Bunds for Euro Area
    }

    COUNTRY_MATCH_TOKENS = {
        "BE": ("BE", "BELGIUM", "BELGIQUE", "BELGIE"),
        "DE": ("DE", "GERMANY", "DEUTSCHLAND", "BUND"),
        "ES": ("ES", "SPAIN", "ESPANA", "SPANISH"),
        "FR": ("FR", "FRANCE", "FRENCH"),
        "GB": ("GB", "UK", "UNITED KINGDOM", "BRITAIN", "GILT"),
        "IT": ("IT", "ITALY", "ITALIA", "ITALIAN"),
        "NL": ("NL", "NETHERLANDS", "DUTCH"),
        "U2": ("U2", "EURO AREA", "EUROZONE"),
    }

    VERIFIED_RISK_FREE_SERIES: Dict[str, Dict[str, str]] = {
        "BE": {
            "dataflow": "YC",
            "series_key": "YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y",
            "benchmark_ref_area": "U2",
            "benchmark_label": "Euro area AAA 10Y spot rate",
        },
        "DE": {
            "dataflow": "YC",
            "series_key": "YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y",
            "benchmark_ref_area": "U2",
            "benchmark_label": "Euro area AAA 10Y spot rate",
        },
        "ES": {
            "dataflow": "YC",
            "series_key": "YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y",
            "benchmark_ref_area": "U2",
            "benchmark_label": "Euro area AAA 10Y spot rate",
        },
        "EU": {
            "dataflow": "YC",
            "series_key": "YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y",
            "benchmark_ref_area": "U2",
            "benchmark_label": "Euro area AAA 10Y spot rate",
        },
        "FR": {
            "dataflow": "YC",
            "series_key": "YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y",
            "benchmark_ref_area": "U2",
            "benchmark_label": "Euro area AAA 10Y spot rate",
        },
        "IT": {
            "dataflow": "YC",
            "series_key": "YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y",
            "benchmark_ref_area": "U2",
            "benchmark_label": "Euro area AAA 10Y spot rate",
        },
        "NL": {
            "dataflow": "YC",
            "series_key": "YC.B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y",
            "benchmark_ref_area": "U2",
            "benchmark_label": "Euro area AAA 10Y spot rate",
        },
        "UK": {
            "dataflow": "IRS",
            "series_key": "IRS.M.GB.L.L40.CI.0000.GBP.N.Z",
            "benchmark_ref_area": "GB",
            "benchmark_label": "United Kingdom 10Y convergence rate",
        },
    }

    def __init__(self, api_key: Optional[str] = None) -> None:
        """
        Initialize ECB adapter

        Args:
            api_key: Not required for ECB public API
        """
        super().__init__(
            base_url=settings.ecb_base_url,
            api_key=None,  # ECB doesn't require API key
            timeout=30,
            max_retries=3,
            cache_ttl=settings.macro_data_cache_ttl,  # 24 hours
        )

    def _get_bond_country(self, country: str) -> str:
        """
        Get appropriate bond country for risk-free rate

        Args:
            country: 2-letter ISO country code

        Returns:
            Country code for bond yields
        """
        country_upper = country.upper()
        if country_upper not in self.BOND_COUNTRY_CODES:
            logger.warning(
                "Country not found, using German Bunds",
                country=country,
                fallback="DE"
            )
            return "DE"  # German Bunds as default risk-free rate

        return self.BOND_COUNTRY_CODES[country_upper]

    async def get_risk_free_rate(
        self,
        country: str,
        maturity_years: int = 10
    ) -> Dict[str, Any]:
        """
        Get risk-free rate (government bond yield)

        For Euro Area countries, German Bunds are typically used as the risk-free rate.
        For UK, use UK Gilts.

        Args:
            country: 2-letter ISO country code
            maturity_years: Bond maturity in years (typically 10)

        Returns:
            Dict with risk-free rate data:
            {
                "country": "DE",
                "maturity_years": 10,
                "yield": 0.025,  # 2.5%
                "yield_date": "2025-10-03",
                "bond_type": "Government Bond",
                "source": "ECB",
                "retrieved_at": "2025-10-03T12:00:00Z"
            }
        """
        requested_country = (country or "").upper() or "DE"
        bond_country = self._get_bond_country(requested_country)
        verified_series = self._get_verified_risk_free_series(requested_country, maturity_years)

        logger.info(
            "Fetching risk-free rate",
            country=requested_country,
            bond_country=bond_country,
            maturity=maturity_years,
            series_resolution="verified_exact" if verified_series else "fallback_lookup",
        )

        try:
            params = {
                "format": "json",
                "lastNObservations": 1,
            }

            if verified_series is not None:
                response = await self._request(
                    "GET",
                    f"data/{verified_series.get('dataflow', self.SERIES_GOV_BOND_10Y)}/{verified_series['series_key']}",
                    params=params,
                )
                selected_series_key = None
                reported_series_key = verified_series["series_key"]
                source = (
                    "ECB Data Portal YC exact series"
                    f" ({verified_series['benchmark_label']})"
                )
                series_resolution = "verified_exact"
                benchmark_ref_area = verified_series["benchmark_ref_area"]
            else:
                logger.warning(
                    "No verified ECB series configured for requested country; using generic selector fallback",
                    country=requested_country,
                    maturity_years=maturity_years,
                )
                response = await self._request(
                    "GET",
                    f"data/{self.SERIES_GOV_BOND_10Y}",
                    params=params,
                )
                selection_country = (
                    verified_series["benchmark_ref_area"] if verified_series else bond_country
                )
                selected_series_key = self._select_government_bond_series_key(
                    response,
                    bond_country=selection_country,
                    maturity_years=maturity_years,
                )
                reported_series_key = selected_series_key
                source = "ECB Data Portal YC generic selector fallback"
                series_resolution = "generic_selector_fallback"
                benchmark_ref_area = selection_country

            if not self.validate_response(response):
                raise ValidationError("Invalid bond yield data format")

            yield_value = self._parse_yield_from_sdmx(response, series_key=selected_series_key)
            _, observation_period = self._extract_latest_observation(
                response,
                series_key=selected_series_key,
            )
            yield_date = observation_period or datetime.now().strftime("%Y-%m-%d")

            result = {
                "country": requested_country,
                "maturity_years": maturity_years,
                "yield": yield_value,
                "yield_date": yield_date,
                "bond_type": f"{maturity_years}-Year Government Bond",
                "source": source,
                "series_key": reported_series_key,
                "series_resolution": series_resolution,
                "benchmark_ref_area": benchmark_ref_area,
                "retrieved_at": datetime.utcnow().isoformat() + "Z",
            }

            logger.info(
                "Risk-free rate retrieved",
                country=requested_country,
                yield_pct=f"{yield_value * 100:.2f}%",
                series_key=reported_series_key,
                series_resolution=series_resolution,
            )

            return result

        except Exception as e:
            logger.error("Failed to fetch risk-free rate", error=str(e), country=requested_country)
            return self._get_fallback_risk_free_rate(requested_country, maturity_years)

    async def get_policy_rate(self) -> Dict[str, Any]:
        """
        Get ECB main refinancing operations rate (policy rate)

        Returns:
            Dict with policy rate data:
            {
                "rate": 0.045,  # 4.5%
                "rate_type": "Main Refinancing Operations",
                "effective_date": "2025-10-03",
                "source": "ECB",
                "retrieved_at": "2025-10-03T12:00:00Z"
            }
        """
        logger.info("Fetching ECB policy rate")

        try:
            endpoint = f"data/{self.SERIES_POLICY_RATE}"

            params = {
                "format": "json",
                "lastNObservations": 1,
            }

            response = await self._request("GET", endpoint, params=params)

            if not self.validate_response(response):
                raise ValidationError("Invalid policy rate data format")

            rate_value = self._parse_rate_from_sdmx(response)

            result = {
                "rate": rate_value,
                "rate_type": "Main Refinancing Operations",
                "effective_date": datetime.now().strftime("%Y-%m-%d"),
                "source": "ECB",
                "retrieved_at": datetime.utcnow().isoformat() + "Z"
            }

            logger.info("Policy rate retrieved", rate_pct=f"{rate_value * 100:.2f}%")

            return result

        except ValuationRangeError as e:
            logger.error("Failed to fetch policy rate", error=str(e))
            return self._get_fallback_policy_rate()

    async def get_credit_spread(
        self,
        rating: str = "BBB",
        country: str = "EU"
    ) -> Dict[str, Any]:
        """
        Get credit spread over risk-free rate

        Used to adjust cost of debt based on credit quality

        Args:
            rating: Credit rating (AAA, AA, A, BBB, BB, B, CCC)
            country: 2-letter ISO country code

        Returns:
            Dict with credit spread data:
            {
                "rating": "BBB",
                "spread": 0.015,  # 1.5% over risk-free
                "base_rate": 0.025,  # Risk-free rate
                "total_rate": 0.040,  # 4.0% total cost of debt
                "source": "ECB + Estimates",
                "retrieved_at": "2025-10-03T12:00:00Z"
            }
        """
        logger.info("Calculating credit spread", rating=rating, country=country)

        try:
            # Get risk-free rate
            risk_free_data = await self.get_risk_free_rate(country)
            risk_free_rate = risk_free_data["yield"]

            # Get credit spread based on rating
            spread = self._get_credit_spread_by_rating(rating)

            result = {
                "rating": rating,
                "spread": spread,
                "base_rate": risk_free_rate,
                "total_rate": risk_free_rate + spread,
                "source": "ECB + Credit Spread Estimates",
                "retrieved_at": datetime.utcnow().isoformat() + "Z"
            }

            logger.info(
                "Credit spread calculated",
                rating=rating,
                spread_pct=f"{spread * 100:.2f}%",
                total_rate_pct=f"{result['total_rate'] * 100:.2f}%"
            )

            return result

        except Exception as e:
            logger.error("Failed to calculate credit spread", error=str(e))
            return self._get_fallback_credit_spread(rating)

    def _get_verified_risk_free_series(
        self,
        country: str,
        maturity_years: int,
    ) -> Optional[Dict[str, str]]:
        """
        Return a verified exact-series mapping for the requested market.

        For Eurozone SMEs we intentionally use the ECB's euro area AAA 10Y
        yield curve as the clean risk-free benchmark rather than embedding
        sovereign credit spread from a single issuer.
        """
        if maturity_years != 10:
            return None
        return self.VERIFIED_RISK_FREE_SERIES.get(country.upper())

    def _parse_yield_from_sdmx(self, response: Dict, series_key: Optional[str] = None) -> Decimal:
        """
        Parse bond yield from ECB SDMX response

        Returns:
            Yield as decimal (e.g., 0.025 for 2.5%)
        """
        try:
            observation_value, _ = self._extract_latest_observation(response, series_key=series_key)
            return self._normalize_rate_value(observation_value)
        except Exception as e:
            logger.error("Failed to parse yield", error=str(e))
            return Decimal("0.025")

    def _parse_rate_from_sdmx(self, response: Dict) -> Decimal:
        """Parse policy rate from SDMX response"""
        try:
            observation_value, _ = self._extract_latest_observation(response)
            return self._normalize_rate_value(observation_value)
        except Exception as e:
            logger.error("Failed to parse rate", error=str(e))
            return Decimal("0.045")

    def _extract_latest_observation(
        self,
        response: Dict,
        series_key: Optional[str] = None,
    ) -> tuple[Any, Optional[str]]:
        """
        Extract the most recent SDMX observation value and period.

        Supports standard SDMX-JSON payloads shaped as:
        {
            "dataSets": [{"series": {"0:0:0": {"observations": {"0": [2.53]}}}}],
            "structure": {"dimensions": {"observation": [{"values": [{"id": "2025-03"}]}]}}
        }
        """
        payload = response.get("data") if isinstance(response.get("data"), dict) else response
        data_sets = payload.get("dataSets") or []
        if not data_sets:
            raise ValidationError("Missing dataSets in ECB response")

        series_map = data_sets[0].get("series") or {}
        if not series_map:
            raise ValidationError("Missing series in ECB response")

        selected_series_key = series_key
        if selected_series_key is None:
            selected_series_key = next(iter(series_map.keys()))
        if selected_series_key not in series_map:
            raise ValidationError(f"Series '{selected_series_key}' not found in ECB response")

        observations = (series_map[selected_series_key] or {}).get("observations") or {}
        if not observations:
            raise ValidationError("Missing observations in ECB response")

        observation_key = sorted(observations.keys(), key=lambda item: int(str(item).split(":")[0]))[-1]
        observation = observations[observation_key]
        if isinstance(observation, list):
            observation_value = observation[0]
        else:
            observation_value = observation

        period = None
        try:
            observation_dimensions = (
                payload.get("structure", {})
                .get("dimensions", {})
                .get("observation", [])
            )
            if observation_dimensions and observation_dimensions[0].get("values"):
                values = observation_dimensions[0]["values"]
                period_idx = int(str(observation_key).split(":")[0])
                if 0 <= period_idx < len(values):
                    period = values[period_idx].get("id") or values[period_idx].get("name")
        except Exception:
            period = None

        return observation_value, period

    def _select_government_bond_series_key(
        self,
        response: Dict,
        *,
        bond_country: str,
        maturity_years: int,
    ) -> str:
        """Select the bond series matching the requested country and maturity."""
        payload = response.get("data") if isinstance(response.get("data"), dict) else response
        data_sets = payload.get("dataSets") or []
        if not data_sets:
            raise ValidationError("Missing dataSets in ECB response")

        series_map = data_sets[0].get("series") or {}
        if not series_map:
            raise ValidationError("Missing series in ECB response")

        if len(series_map) == 1:
            return next(iter(series_map.keys()))

        series_dimensions = (
            payload.get("structure", {})
            .get("dimensions", {})
            .get("series", [])
        )
        country_tokens = self.COUNTRY_MATCH_TOKENS.get(bond_country, (bond_country,))
        maturity_tokens = (
            f"{maturity_years}Y",
            f"{maturity_years}-YEAR",
            f"{maturity_years} YEAR",
            f"{maturity_years} YEARS",
            str(maturity_years),
        )

        best_key: Optional[str] = None
        best_score = -1

        for key in series_map:
            descriptor = self._series_descriptor_blob(key, series_dimensions)
            score = 0

            if any(token in descriptor for token in country_tokens):
                score += 2
            if any(token in descriptor for token in maturity_tokens):
                score += 2
            if "GOV" in descriptor or "GOVERNMENT" in descriptor or "BOND" in descriptor:
                score += 1

            if score > best_score:
                best_score = score
                best_key = key

        if best_key is None or best_score < 4:
            raise ValidationError(
                f"Could not identify {bond_country} {maturity_years}Y bond series from ECB payload"
            )

        return best_key

    def _series_descriptor_blob(self, series_key: str, series_dimensions: List[Dict[str, Any]]) -> str:
        """Flatten SDMX series-dimension metadata into an uppercase search blob."""
        parts = str(series_key).split(":")
        tokens: List[str] = [str(series_key)]

        for idx, raw_part in enumerate(parts):
            try:
                value_index = int(raw_part)
            except (TypeError, ValueError):
                tokens.append(str(raw_part))
                continue

            if idx >= len(series_dimensions):
                continue

            values = series_dimensions[idx].get("values") or []
            if 0 <= value_index < len(values):
                value = values[value_index] or {}
                tokens.extend(
                    str(value.get(field, ""))
                    for field in ("id", "name")
                    if value.get(field) is not None
                )

        return " ".join(tokens).upper()

    def _normalize_rate_value(self, raw_value: Any) -> Decimal:
        """Normalize SDMX percentage-like values to decimal form."""
        value = Decimal(str(raw_value))
        if value > Decimal("1"):
            value = value / Decimal("100")
        return value

    def _get_credit_spread_by_rating(self, rating: str) -> Decimal:
        """
        Get credit spread based on credit rating

        Spreads over risk-free rate (typical values for European corporates)
        """
        spreads = {
            "AAA": Decimal("0.005"),  # 0.5% (50 bps)
            "AA": Decimal("0.008"),   # 0.8% (80 bps)
            "A": Decimal("0.012"),    # 1.2% (120 bps)
            "BBB": Decimal("0.020"),  # 2.0% (200 bps)
            "BB": Decimal("0.035"),   # 3.5% (350 bps)
            "B": Decimal("0.055"),    # 5.5% (550 bps)
            "CCC": Decimal("0.090"),  # 9.0% (900 bps)
            "DEFAULT": Decimal("0.025"),  # 2.5% (250 bps) default
        }

        return spreads.get(rating.upper(), spreads["DEFAULT"])

    def _get_fallback_risk_free_rate(
        self,
        country: str,
        maturity_years: int
    ) -> Dict[str, Any]:
        """Fallback risk-free rate when API fails"""
        # Use reasonable estimates based on current market conditions
        fallback_rates = {
            "DE": Decimal("0.025"),  # 2.5% German Bund
            "FR": Decimal("0.030"),  # 3.0% French OAT
            "GB": Decimal("0.040"),  # 4.0% UK Gilt
            "NL": Decimal("0.027"),  # 2.7% Netherlands
            "ES": Decimal("0.032"),  # 3.2% Spain
            "IT": Decimal("0.038"),  # 3.8% Italy
            "EU": Decimal("0.025"),  # 2.5% Default to Bund
        }

        bond_country = self._get_bond_country(country)
        yield_value = fallback_rates.get(bond_country, Decimal("0.030"))

        return {
            "country": bond_country,
            "maturity_years": maturity_years,
            "yield": yield_value,
            "yield_date": datetime.now().strftime("%Y-%m-%d"),
            "bond_type": f"{maturity_years}-Year Government Bond",
            "source": "Fallback (ECB API unavailable)",
            "series_resolution": "fallback_static",
            "benchmark_ref_area": bond_country,
            "retrieved_at": datetime.utcnow().isoformat() + "Z",
            "is_fallback": True
        }

    def _get_fallback_policy_rate(self) -> Dict[str, Any]:
        """Fallback policy rate when API fails"""
        return {
            "rate": Decimal("0.045"),  # 4.5% current estimate
            "rate_type": "Main Refinancing Operations",
            "effective_date": datetime.now().strftime("%Y-%m-%d"),
            "source": "Fallback (ECB API unavailable)",
            "retrieved_at": datetime.utcnow().isoformat() + "Z",
            "is_fallback": True
        }

    def _get_fallback_credit_spread(self, rating: str) -> Dict[str, Any]:
        """Fallback credit spread when API fails"""
        risk_free_rate = Decimal("0.025")  # 2.5% fallback
        spread = self._get_credit_spread_by_rating(rating)

        return {
            "rating": rating,
            "spread": spread,
            "base_rate": risk_free_rate,
            "total_rate": risk_free_rate + spread,
            "source": "Fallback (ECB API unavailable)",
            "retrieved_at": datetime.utcnow().isoformat() + "Z",
            "is_fallback": True
        }

    async def test_connection(self) -> bool:
        """
        Test connection to ECB API

        Returns:
            True if connection successful
        """
        try:
            await self.get_risk_free_rate("DE", maturity_years=10)
            logger.info("ECB API connection successful")
            return True
        except DataValidationError as e:
            logger.error("ECB API connection failed", error=str(e))
            return False

    def validate_response(self, data: Any) -> bool:
        """
        Validate ECB API response

        Args:
            data: Response data to validate

        Returns:
            True if valid
        """
        if not isinstance(data, dict):
            return False

        # Basic validation
        return True

