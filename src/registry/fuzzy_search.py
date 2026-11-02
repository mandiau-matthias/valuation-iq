"""
Fuzzy Search and Suggestion Engine

Provides elastic/suggestive search capabilities for company names with:
- Fuzzy string matching
- Partial name matching
- Common variations and abbreviations
- Typo tolerance
- Search suggestions
"""

import re
from typing import List, Dict, Any, Tuple, Optional
from difflib import SequenceMatcher
from src.utils.logging import get_logger
from decimal import Decimal

logger = get_logger(__name__)


class FuzzySearchEngine:
    """
    Advanced fuzzy search engine for company names.

    Features:
    - Fuzzy string matching with configurable thresholds
    - Common business name variations (Ltd, Inc, Corp, etc.)
    - Partial matching and word-based matching
    - Typo tolerance with edit distance
    - Search suggestions and alternatives
    """

    def __init__(self, similarity_threshold: Decimal = 0.6):
        """Initialize fuzzy search engine."""
        self.similarity_threshold = similarity_threshold

        # Common business suffixes and their variations
        self.business_suffixes = {
            'ltd': ['limited', 'ltd', 'ltd.', 'lt'],
            'inc': ['incorporated', 'inc', 'inc.', 'corp', 'corporation'],
            'bv': ['besloten vennootschap', 'bv', 'bvba'],
            'gmbh': ['gesellschaft mit beschränkter haftung', 'gmbh'],
            'sa': ['société anonyme', 'sa', 's.a.'],
            'sarl': ['société à responsabilité limitée', 'sarl', 's.a.r.l.'],
            'nv': ['naamloze vennootschap', 'nv', 'n.v.'],
            'bvba': ['besloten vennootschap met beperkte aansprakelijkheid', 'bvba'],
            'sprl': ['société privée à responsabilité limitée', 'sprl'],
            'plc': ['public limited company', 'plc', 'p.l.c.'],
            'llc': ['limited liability company', 'llc', 'l.l.c.'],
            'ag': ['aktiengesellschaft', 'ag', 'a.g.'],
            'kg': ['kommanditgesellschaft', 'kg', 'k.g.'],
            'ohg': ['offene handelsgesellschaft', 'ohg', 'o.h.g.'],
            'ug': ['unternehmergesellschaft', 'ug', 'u.g.'],
            'bvba': ['besloten vennootschap met beperkte aansprakelijkheid', 'bvba'],
            'cv': ['commanditaire vennootschap', 'cv', 'c.v.'],
            'vof': ['vennootschap onder firma', 'vof', 'v.o.f.'],
            'eenmanszaak': ['eenmanszaak', 'eenmanszaak bv'],
            'stichting': ['stichting', 'stg', 'stg.'],
            'vereniging': ['vereniging', 'ver.', 'ver'],
            'coöperatie': ['coöperatie', 'coop', 'coöperatie ua'],
            'onderlinge': ['onderlinge waarborgmaatschappij', 'onderlinge'],
        }

        # Common company name variations and abbreviations
        self.name_variations = {
            'motor': ['motors', 'motoren', 'automotive', 'auto'],
            'technology': ['tech', 'technologies', 'technologie', 'technologies'],
            'international': ['intl', 'int\'l', 'international', 'internationaal'],
            'europe': ['european', 'europe', 'europa', 'eu'],
            'group': ['grp', 'group', 'groep', 'holding'],
            'services': ['service', 'services', 'diensten', 'service'],
            'solutions': ['solution', 'solutions', 'oplossingen'],
            'systems': ['system', 'systems', 'systemen'],
            'consulting': ['consultancy', 'consulting', 'consultants'],
            'management': ['mgmt', 'management', 'beheer'],
            'development': ['dev', 'development', 'ontwikkeling'],
            'engineering': ['eng', 'engineering', 'ingenieursbureau'],
            'construction': ['construction', 'bouw', 'bouwbedrijf'],
            'trading': ['trade', 'trading', 'handel'],
            'investment': ['investments', 'investment', 'beleggingen'],
            'financial': ['finance', 'financial', 'financieel'],
            'holding': ['holdings', 'holding', 'beheer'],
            'partners': ['partner', 'partners', 'partnerschap'],
            'associates': ['associate', 'associates', 'associés'],
            'enterprises': ['enterprise', 'enterprises', 'onderneming'],
            'industries': ['industry', 'industries', 'industrie'],
            'manufacturing': ['manufacturer', 'manufacturing', 'productie'],
            'distribution': ['distributor', 'distribution', 'distributie'],
            'logistics': ['logistic', 'logistics', 'logistiek'],
            'marketing': ['market', 'marketing', 'marketing'],
            'advertising': ['advertise', 'advertising', 'reclame'],
            'media': ['medium', 'media', 'media'],
            'communications': ['communication', 'communications', 'communicatie'],
            'telecommunications': ['telecom', 'telecommunications', 'telecommunicatie'],
            'software': ['soft', 'software', 'programmatuur'],
            'hardware': ['hard', 'hardware', 'hardware'],
            'electronics': ['electronic', 'electronics', 'elektronica'],
            'pharmaceuticals': ['pharma', 'pharmaceuticals', 'farmaceutisch'],
            'biotechnology': ['biotech', 'biotechnology', 'biotechnologie'],
            'energy': ['energie', 'energy', 'energie'],
            'renewable': ['renewables', 'renewable', 'hernieuwbaar'],
            'environmental': ['environment', 'environmental', 'milieu'],
            'sustainability': ['sustainable', 'sustainability', 'duurzaamheid'],
            'innovation': ['innovative', 'innovation', 'innovatie'],
            'research': ['r&d', 'research', 'onderzoek'],
            'development': ['r&d', 'development', 'ontwikkeling'],
        }

    def generate_search_variations(self, company_name: str) -> List[str]:
        """
        Generate multiple search variations for a company name.

        Args:
            company_name: Original company name

        Returns:
            List of search variations
        """
        variations = [company_name.strip()]
        name_lower = company_name.lower().strip()

        # Add original with different casing
        variations.extend([
            company_name.title(),
            company_name.upper(),
            company_name.lower()
        ])

        # Generate variations by replacing common words
        for original, alternatives in self.name_variations.items():
            if original in name_lower:
                for alt in alternatives:
                    if alt != original:
                        variation = name_lower.replace(original, alt)
                        variations.append(variation.title())

        # Generate variations by adding/removing business suffixes
        for suffix_group in self.business_suffixes.values():
            for suffix in suffix_group:
                if name_lower.endswith(suffix):
                    # Remove suffix
                    base_name = name_lower[:-len(suffix)].strip()
                    if base_name:
                        variations.append(base_name.title())

                    # Replace with other suffixes in the same group
                    for other_suffix in suffix_group:
                        if other_suffix != suffix:
                            new_name = base_name + ' ' + other_suffix
                            variations.append(new_name.title())
                    break

        # Add partial matches (first word, first two words, etc.)
        words = name_lower.split()
        if len(words) > 1:
            variations.append(words[0].title())  # First word only
            if len(words) > 2:
                variations.append(' '.join(words[:2]).title())  # First two words

        # Remove duplicates and empty strings
        variations = list(set([v for v in variations if v.strip()]))

        logger.debug("Generated search variations", 
                    original=company_name, 
                    variations=variations)

        return variations

    def calculate_similarity(self, name1: str, name2: str) -> Decimal:
        """
        Calculate similarity between two company names.

        Args:
            name1: First company name
            name2: Second company name

        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Normalize names
        norm1 = self._normalize_name(name1)
        norm2 = self._normalize_name(name2)

        # Exact match
        if norm1 == norm2:
            return 1.0

        # Use SequenceMatcher for fuzzy matching
        similarity = SequenceMatcher(None, norm1, norm2).ratio()

        # Boost score for partial matches
        if norm1 in norm2 or norm2 in norm1:
            similarity = max(similarity, 0.8)

        # Boost score for word-based matches
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        if words1 and words2:
            word_similarity = len(words1.intersection(words2)) / len(words1.union(words2))
            similarity = max(similarity, word_similarity * 0.9)

        return similarity

    def _normalize_name(self, name: str) -> str:
        """
        Normalize company name for comparison.

        Args:
            name: Company name to normalize

        Returns:
            Normalized name
        """
        # Convert to lowercase
        normalized = name.lower().strip()

        # Remove common punctuation
        normalized = re.sub(r'[.,;:!?]', '', normalized)

        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)

        # Remove common business suffixes for comparison
        for suffix_group in self.business_suffixes.values():
            for suffix in suffix_group:
                if normalized.endswith(' ' + suffix):
                    normalized = normalized[:-len(' ' + suffix)].strip()
                    break

        return normalized

    def find_best_matches(
        self, 
        search_term: str, 
        candidates: List[str], 
        limit: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Find best fuzzy matches for a search term.

        Args:
            search_term: Term to search for
            candidates: List of candidate company names
            limit: Maximum number of results

        Returns:
            List of (company_name, similarity_score) tuples
        """
        matches = []

        for candidate in candidates:
            similarity = self.calculate_similarity(search_term, candidate)
            if similarity >= self.similarity_threshold:
                matches.append((candidate, similarity))

        # Sort by similarity score (highest first)
        matches.sort(key=lambda x: x[1], reverse=True)

        return matches[:limit]

    def generate_search_suggestions(
        self, 
        search_term: str, 
        failed_searches: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate helpful search suggestions when no results are found.

        Args:
            search_term: Original search term
            failed_searches: List of search variations that were tried

        Returns:
            List of suggestion dictionaries
        """
        suggestions = []

        # Generate search variations
        variations = self.generate_search_variations(search_term)

        # Remove variations that were already tried
        if failed_searches:
            variations = [v for v in variations if v.lower() not in [fs.lower() for fs in failed_searches]]

        # Create suggestion objects
        for i, variation in enumerate(variations[:5]):  # Limit to 5 suggestions
            if variation.lower() != search_term.lower():
                suggestions.append({
                    'suggestion': variation,
                    'reason': self._get_suggestion_reason(search_term, variation),
                    'confidence': 0.8 - (i * 0.1)  # Decreasing confidence
                })

        # Add generic suggestions
        suggestions.extend([
            {
                'suggestion': f'Try searching for "{search_term}" with registration number',
                'reason': 'Registration numbers are more precise',
                'confidence': 0.7
            },
            {
                'suggestion': f'Try different spelling of "{search_term}"',
                'reason': 'Company names might be spelled differently',
                'confidence': 0.6
            },
            {
                'suggestion': 'Try searching without business suffixes (Ltd, Inc, etc.)',
                'reason': 'Some companies are registered without suffixes',
                'confidence': 0.5
            }
        ])

        return suggestions

    def _get_suggestion_reason(self, original: str, variation: str) -> str:
        """Get a human-readable reason for a suggestion."""
        original_lower = original.lower()
        variation_lower = variation.lower()

        if len(variation_lower) < len(original_lower):
            return "Shorter version might work better"
        elif len(variation_lower) > len(original_lower):
            return "More complete name might help"
        elif variation_lower != original_lower:
            return "Alternative spelling or abbreviation"
        else:
            return "Try this variation"


class SearchSuggestionService:
    """
    Service for providing intelligent search suggestions.

    This service can be extended to integrate with external APIs
    for company name suggestions, common misspellings, etc.
    """

    def __init__(self):
        """Initialize search suggestion service."""
        self.fuzzy_engine = FuzzySearchEngine()
        self.logger = get_logger(__name__)

    async def get_search_suggestions(
        self, 
        company_name: str, 
        country_code: str = "BE"
    ) -> List[Dict[str, Any]]:
        """
        Get intelligent search suggestions for a company name.

        Args:
            company_name: Company name to get suggestions for
            country_code: Country code for context

        Returns:
            List of suggestion dictionaries
        """
        self.logger.info("Generating search suggestions", 
                        company_name=company_name, 
                        country_code=country_code)

        # Generate fuzzy search variations
        variations = self.fuzzy_engine.generate_search_variations(company_name)

        # Create suggestion objects
        suggestions = []
        for variation in variations[:8]:  # Limit to 8 suggestions
            if variation.lower() != company_name.lower():
                suggestions.append({
                    'text': variation,
                    'type': 'variation',
                    'confidence': 0.8,
                    'reason': f'Try "{variation}" instead'
                })

        # Add country-specific suggestions
        if country_code == "BE":
            suggestions.extend([
                {
                    'text': f'Search for "{company_name}" in French',
                    'type': 'language',
                    'confidence': 0.7,
                    'reason': 'Belgian companies often have French names'
                },
                {
                    'text': f'Search for "{company_name}" in Dutch',
                    'type': 'language', 
                    'confidence': 0.7,
                    'reason': 'Belgian companies often have Dutch names'
                }
            ])

        # Add generic helpful suggestions
        suggestions.extend([
            {
                'text': 'Try with registration number',
                'type': 'method',
                'confidence': 0.9,
                'reason': 'Registration numbers are more precise than names'
            },
            {
                'text': 'Check company name spelling',
                'type': 'method',
                'confidence': 0.8,
                'reason': 'Small spelling differences can prevent matches'
            },
            {
                'text': 'Try without business suffixes (BV, SA, etc.)',
                'type': 'method',
                'confidence': 0.7,
                'reason': 'Some companies are registered without legal suffixes'
            }
        ])

        return suggestions
