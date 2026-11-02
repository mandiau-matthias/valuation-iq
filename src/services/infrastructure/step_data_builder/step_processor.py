"""
Step Processor

Processes individual step outputs (dict or object) into standardized format.
"""

from typing import Dict, Any, Optional
from decimal import Decimal

from src.utils.logging import get_logger
from src.utils.decimal_helpers import to_decimal
from .academic_source_extractor import AcademicSourceExtractor
from .utils import ensure_step_outputs_defaults

logger = get_logger(__name__)


class StepProcessor:
    """Processes individual step outputs."""

    VALID_STATUSES = {'completed', 'skipped', 'failed', 'not_executed'}

    @staticmethod
    def process_step(
        step_output: Any,
        step_number: int,
    ) -> Dict[str, Any]:
        """
        Process a step output (dict or object) into standardized format.

        Args:
            step_output: Step output (dict or object)
            step_number: Step number (0-11)

        Returns:
            Dictionary containing processed step data
        """
        if isinstance(step_output, dict):
            return StepProcessor._process_dict_step(step_output, step_number)
        else:
            return StepProcessor._process_object_step(step_output, step_number)

    @staticmethod
    def _process_dict_step(step_output: Dict[str, Any], step_number: int) -> Dict[str, Any]:
        """Process dict-based step output."""
        # Validate and normalize status
        raw_status = step_output.get('status', 'completed')
        step_status = StepProcessor._normalize_status(
            str(raw_status).lower(),
            step_number
        )
        # BANK-GRADE: Log status for Step 10 and 11 to debug status issues
        if step_number >= 10:
            logger.debug(
                f"Step {step_number} status processing",
                extra={
                    'step_number': step_number,
                    'raw_status': raw_status,
                    'normalized_status': step_status,
                    'status_type': type(raw_status).__name__,
                    'has_error': 'error' in step_output and step_output.get('error') is not None,
                    'error_message': step_output.get('error') if step_output.get('error') else None
                }
            )

        # Validate step_number matches
        step_number_from_data = step_output.get('step_number', step_number)
        if step_number_from_data != step_number:
            logger.warning(
                f"Step number mismatch: expected {step_number}, got {step_number_from_data}",
                extra={'expected_step': step_number, 'actual_step': step_number_from_data}
            )
            step_output['step_number'] = step_number

        # Map 'result' to 'outputs' if result exists and is valid
        StepProcessor._map_result_to_outputs(step_output)

        # Ensure 'outputs' is always a dictionary
        if 'outputs' not in step_output or not isinstance(step_output.get('outputs'), dict):
            step_output['outputs'] = {}

        # Ensure all template-accessed fields exist with defaults
        step_output['outputs'] = ensure_step_outputs_defaults(step_output['outputs'])

        # Ensure inputs is always a dictionary
        if 'inputs' not in step_output or not isinstance(step_output.get('inputs'), dict):
            step_output['inputs'] = {}

        # Ensure metadata is always a dictionary
        if 'metadata' not in step_output or not isinstance(step_output.get('metadata'), dict):
            step_output['metadata'] = {}

        # Extract formula and explanation from metadata
        StepProcessor._extract_formula_fields(step_output)

        # Ensure step_name field exists (template expects this)
        if 'step_name' not in step_output or not step_output.get('step_name'):
            step_output['step_name'] = (
                step_output.get('step_name') or
                step_output.get('calculation_name') or
                step_output.get('metadata', {}).get('step_name') or
                step_output.get('metadata', {}).get('calculation_name') or
                f'Step {step_number}'
            )
        
        # Ensure rationale field exists (template expects this)
        if 'rationale' not in step_output or not step_output.get('rationale'):
            step_output['rationale'] = StepProcessor._extract_rationale(
                step_output, step_number, step_status
            )

        # Extract academic sources
        academic_source_ids, academic_sources = AcademicSourceExtractor.extract_sources(step_number)
        step_output['academic_source_ids'] = academic_source_ids
        step_output['academic_sources'] = academic_sources

        return step_output

    @staticmethod
    def _process_object_step(step_output: Any, step_number: int) -> Dict[str, Any]:
        """Process object-based step output."""
        # Validate and normalize status
        step_status = StepProcessor._normalize_status(
            str(getattr(step_output, 'status', 'completed')).lower(),
            step_number
        )

        # Extract outputs data
        result_data = getattr(step_output, 'result', None)
        outputs_data = getattr(step_output, 'outputs', {})
        final_outputs = (
            result_data
            if result_data is not None and isinstance(result_data, dict) and result_data
            else outputs_data if isinstance(outputs_data, dict) else {}
        )
        if not isinstance(final_outputs, dict):
            final_outputs = {}

        # Ensure all template-accessed fields exist with defaults
        final_outputs = ensure_step_outputs_defaults(final_outputs)

        # Extract inputs data
        inputs_data = getattr(step_output, 'inputs', {})
        if not isinstance(inputs_data, dict):
            inputs_data = {}

        # Extract metadata
        metadata_dict = getattr(step_output, 'metadata', {})
        if not isinstance(metadata_dict, dict):
            metadata_dict = {}

        # Extract formula fields
        formula = (
            metadata_dict.get('formula') or
            final_outputs.get('formula') or
            getattr(step_output, 'formula', '')
        )
        explanation = (
            metadata_dict.get('explanation') or
            final_outputs.get('explanation') or
            getattr(step_output, 'explanation', '')
        )
        formula_explanation = (
            metadata_dict.get('formula_explanation') or
            metadata_dict.get('calculation_explanation') or
            None
        )

        # Extract academic sources
        academic_source_ids, academic_sources = AcademicSourceExtractor.extract_sources(step_number)

        # Extract step_name (preferred) or fallback to calculation_name
        step_name = getattr(
            step_output,
            'step_name',
            getattr(
                step_output,
                'calculation_name',
                metadata_dict.get('step_name') or metadata_dict.get('calculation_name') or f'Step {step_number}'
            )
        )
        
        # Extract rationale (preferred) or fallback to explanation
        # BANK-GRADE: For failed steps, use error message as rationale
        step_status_lower = step_status.lower() if step_status else ''
        error_message = getattr(step_output, 'error', None)
        
        if step_status_lower == 'failed' and error_message:
            # Use error message as rationale for failed steps
            rationale = str(error_message)
        else:
            # Extract rationale using enhanced extraction logic
            # Convert object to dict-like structure for _extract_rationale
            temp_dict = {
                'rationale': getattr(step_output, 'rationale', None),
                'explanation': getattr(step_output, 'explanation', None),
                'error': getattr(step_output, 'error', None),
                'metadata': metadata_dict,
                'outputs': final_outputs,
            }
            rationale = StepProcessor._extract_rationale(temp_dict, step_number, step_status)
        
        # Build step dictionary
        return {
            'step_number': step_number,
            'step_name': step_name,  # Template expects this field
            'calculation_name': getattr(
                step_output,
                'calculation_name',
                metadata_dict.get('calculation_name', step_name)
            ),
            'formula': formula,
            'formula_explanation': formula_explanation,
            'inputs': inputs_data,
            'output': to_decimal(
                getattr(step_output, 'output', final_outputs.get('output', 0) or 0) or 0
            ),
            'outputs': final_outputs,
            'explanation': explanation,
            'rationale': rationale,  # Template expects this field
            'metadata': metadata_dict,
            'status': step_status,
            'skip_reason': getattr(step_output, 'skip_reason', None),
            'error': getattr(step_output, 'error', None),
            'academic_source_ids': academic_source_ids,
            'academic_sources': academic_sources,
        }

    @staticmethod
    def _normalize_status(status: str, step_number: int) -> str:
        """Normalize step status to valid value."""
        if status not in StepProcessor.VALID_STATUSES:
            logger.warning(
                f"Step {step_number} has unexpected status: {status}, defaulting to 'completed'",
                extra={'step_number': step_number, 'unexpected_status': status}
            )
            return 'completed'
        return status

    @staticmethod
    def _map_result_to_outputs(step_output: Dict[str, Any]) -> None:
        """Map 'result' field to 'outputs' if result exists and is valid."""
        if 'result' in step_output and step_output.get('result') is not None:
            result_data = step_output.get('result')
            # Only map if result is a non-empty dict
            if isinstance(result_data, dict) and result_data:
                step_output['outputs'] = result_data

    @staticmethod
    def _extract_formula_fields(step_output: Dict[str, Any]) -> None:
        """Extract formula and explanation from metadata if not already in step_output."""
        metadata = step_output.get('metadata', {})
        outputs = step_output.get('outputs', {})

        if 'formula' not in step_output or not step_output.get('formula'):
            step_output['formula'] = (
                metadata.get('formula') or
                outputs.get('formula') or
                ''
            )

        if 'explanation' not in step_output or not step_output.get('explanation'):
            step_output['explanation'] = (
                metadata.get('explanation') or
                outputs.get('explanation') or
                ''
            )

        if 'formula_explanation' not in step_output:
            step_output['formula_explanation'] = (
                metadata.get('formula_explanation') or
                metadata.get('calculation_explanation') or
                None
            )

    @staticmethod
    def _extract_rationale(step_output: dict, step_number: int, step_status: str) -> str:
        """
        Extract meaningful rationale from step output.
        Handles both string and dict-based explanations.
        
        Args:
            step_output: Step output dictionary
            step_number: Step number (0-11)
            step_status: Normalized step status
            
        Returns:
            Formatted rationale string
        """
        # For failed steps, prioritize error message
        if step_status == 'failed' and step_output.get('error'):
            return f"❌ Failed: {step_output.get('error')}"
        
        # Try various rationale fields in order of preference
        rationale_fields = [
            step_output.get('rationale'),
            step_output.get('explanation'),
            step_output.get('metadata', {}).get('rationale'),
            step_output.get('metadata', {}).get('explanation'),
            step_output.get('metadata', {}).get('detailed_explanation'),
            step_output.get('outputs', {}).get('detailed_explanation'),
            step_output.get('outputs', {}).get('explanation'),
            step_output.get('outputs', {}).get('rationale'),
        ]
        
        for field in rationale_fields:
            if field and isinstance(field, str) and field.strip():
                return field.strip()
            elif field and isinstance(field, dict):
                # Format dict-based explanations (e.g., Step 4)
                formatted = StepProcessor._format_dict_rationale(field, step_number)
                if formatted:
                    return formatted
        
        # Step-specific fallback messages
        return StepProcessor._get_step_specific_fallback(step_number, step_status, step_output)

    @staticmethod
    def _format_dict_rationale(rationale_dict: dict, step_number: int) -> str:
        """
        Format dict-based rationale into readable text.
        
        Args:
            rationale_dict: Dictionary containing rationale data
            step_number: Step number for step-specific formatting
            
        Returns:
            Formatted rationale string
        """
        # Step 4 (Owner Concentration) has structured dict with 'logic' field
        if step_number == 4:
            logic = rationale_dict.get('logic')
            if logic and isinstance(logic, str):
                return logic
            
            # Fallback: construct from components
            percentage = rationale_dict.get('percentage')
            risk_level = rationale_dict.get('risk_level')
            if percentage and risk_level:
                return f"Applied {percentage}% adjustment based on {risk_level} key person risk"
        
        # Generic dict formatting - try common explanation keys
        for key in ['logic', 'explanation', 'summary', 'description', 'note']:
            value = rationale_dict.get(key)
            if value and isinstance(value, str) and value.strip():
                return value.strip()
        
        # Last resort: format key fields as bullet points
        bullets = []
        for key, value in rationale_dict.items():
            if isinstance(value, (str, int, float)) and not key.startswith('_'):
                bullets.append(f"{key.replace('_', ' ').title()}: {value}")
        
        if bullets:
            return " | ".join(bullets[:3])  # Limit to first 3 items
        
        return ""  # Empty string will trigger fallback

    @staticmethod
    def _get_step_specific_fallback(step_number: int, step_status: str, step_output: dict) -> str:
        """
        Get step-specific fallback message instead of generic "Step X calculation completed".
        
        Args:
            step_number: Step number (0-11)
            step_status: Normalized step status
            step_output: Step output dictionary
            
        Returns:
            Step-specific helpful fallback message
        """
        if step_status == 'skipped':
            return "Skipped (not applicable for this valuation)"
        
        # Step-specific meaningful fallbacks
        fallbacks = {
            0: "Data quality assessment completed successfully",
            1: "Financial data and business profile validated",
            2: "Industry benchmarks and valuation multiples selected from comparables",
            3: "Base enterprise value calculated. Quality calibration applied to multiple (Step 2.5). Multiple adjusted from comparable base to company-specific calibrated multiple.",
            4: "Multiple discounted for owner concentration risk. Adjustment applied to valuation multiple, not EBITDA.",
            5: "Multiple discounted for company size. Size premium/discount applied to valuation multiple.",
            6: "Multiple discounted for illiquidity. Private company liquidity discount applied to valuation multiple.",
            7: "Enterprise value converted to equity value (EV - Net Debt)",
            8: "Ownership percentage adjustment applied to equity value",
            9: "Valuation confidence score calculated based on data quality and methodology strength",
            10: "Range methodology determined and applied to equity value",
            11: "Final valuation range synthesized. Multiple-first methodology ensures no double-counting."
        }
        
        return fallbacks.get(step_number, f"Step {step_number} calculation completed")

