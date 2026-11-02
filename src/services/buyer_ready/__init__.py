"""Buyer-Ready Package math services (BET-240 Epic F).

Pure math modules for the buyer-ready package deliverable. No I/O,
no DB, no service calls — just deterministic computation.

Modules:
    wc_peg.py       — F5 Part A. Working-capital peg target from monthly
                      or annual NWC signals.
    tax_latency.py  — F5 Part B. 10 jurisdiction rules (7 BE + 3 NL) that
                      flag latent tax issues before legal handoff.

Both feed the F1 render payload (`buyer_ready_models.WCPegRender` +
`TaxLatencyRender`) — Titan-side orchestration projects engine output
into the render shape; ValuationIQ here owns only the math.
"""
