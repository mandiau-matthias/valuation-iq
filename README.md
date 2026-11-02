# ValuationIQ

**[Open a sample valuation PDF](examples/report.pdf)** · [Edit the fictional company](examples/company.json) · [Inspect its calculation](examples/valuation.json)

I built this engine with accountants at Upswitch. Given a company's financials and the assumptions behind its valuation, it calculates a range and shows how enterprise value becomes equity value. This edition runs on your computer. Canal Works and every comparable in the tutorial are fictional.

### Run it locally

From this repository, run **`make example`**. The first run installs the pinned Python dependencies, then writes `output/report.pdf` and `output/valuation.json`. Later runs reuse the environment. For another company, copy the example and run `make example CASE=your-company.json OUT=your-report`. The calculation and reporting command blocks outgoing network connections. The initial dependency installation needs internet access.

Prerequisites are Python 3.11, Make, and WeasyPrint's native Pango libraries. On macOS these are available through Homebrew (`brew install python@3.11 pango`). On Debian with Python 3.11 install `python3-venv make libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core`. [WeasyPrint installation guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation)

### What to enter

| For the operating-company example | Where it goes |
|---|---|
| Name, operating country, currency, industry, business model, founding year | Top-level company fields. All amounts use the stated currency in whole units. |
| Fiscal year, revenue, EBITDA | `current_year`. Earlier comparable years go in `historical_years`. A recorded zero is a supplied amount. An omitted required value fails validation. |
| Cash and interest-bearing debt | `current_year.cash` and `current_year.total_debt` reconcile operating value to equity. |
| Sector assumptions and market multiples | `business_type_calibration`. For a multiples method, include both the distribution and matching benchmark evidence. Replace the tutorial evidence with your own appropriately licensed inputs. |

Method-specific inputs matter. DCF needs cash-flow assumptions, discounting and terminal growth. Adjusted net assets needs assets and liabilities. The startup methods need stage, traction and qualitative inputs along with regional reference assumptions. The full [calculation request](src/api/schemas/stateless_api.py), [method registry](contracts/valuation-methods.v1.json), and [independent reference calculations](tests/reference/reference_math.py) are included.

### Change one assumption

The example supplies €25,000 cash and €100,000 debt. Its enterprise value is **€896,325** and its equity value is **€821,325**. Change only `current_year.cash` to `"35000"` and rerun. Enterprise value stays €896,325 and equity rises to **€831,325**. Find the full amounts in the PDF’s EV-to-equity bridge and in the JSON fields `enterprise_value_mid` and `equity_value_mid`.

### Use your own reference data

The sample runs without a vendor account. Supply market data at the point of use. For startup valuations, `VALUATIONIQ_REFERENCE_DIR` points to a local directory of JSON files. [Fictional regional and sector examples](examples/references/) illustrate the shape. Optional `startup-sectors.json` overrides regional assumptions by stage and sector. For workbook reconciliation, supply `dcf-standard.json` (sum_pv_fcf, terminal_value, pv_terminal_value, enterprise_value) or `dcf-apv.json` (dcf_enterprise_value, apv_tax_shield_value, apv_enterprise_value, apv_equity_value), with numeric values by metric. Set the matching business-context reference to `local_dcf_standard` or `local_dcf_apv`.

This release includes the original calculation and report source. Original code is MIT. The bundled Noto and JetBrains fonts have their own [Open Font License](src/assets/fonts/OFL.txt). If you find a discrepancy, a fictional input file plus your independently calculated expected result is the most helpful issue.
