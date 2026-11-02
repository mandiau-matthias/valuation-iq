"""
ContextUpdater

Updates conversation context with extracted field values.
"""

import logging
from typing import Any


class ContextUpdater:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def update_collected_data(self, context: Any, field: str, value: Any) -> None:
        self.logger.debug("Updating context field=%s", field)
        context.update_collected_data(field, value)
