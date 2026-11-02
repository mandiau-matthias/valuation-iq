"""Currency transport for legacy responses; independent of presentation language."""

def response_currency(request: object) -> str | None:
    currency = getattr(request, "currency", None)
    if isinstance(currency, str) and len(currency) == 3 and currency.isalpha():
        return currency.upper()
    return None
