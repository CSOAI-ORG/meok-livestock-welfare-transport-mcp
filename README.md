<!-- mcp-name: io.github.CSOAI-ORG/meok-livestock-welfare-transport-mcp -->
[![MCP Scorecard: 90/100](https://img.shields.io/badge/proofof.ai-90%2F100-5b21b6)](https://proofof.ai/scorecard/meok-livestock-welfare-transport-mcp.html)

# meok-livestock-welfare-transport-mcp

> UK + EU animal welfare in transport compliance for livestock hauliers. EU REG 1/2005 long-journey logs, Type 1 vs Type 2 transporter authorisation, driver Certificate of Competence, species-specific vehicle approval + loading density, rest/water/feed cadence, and APHA roadside inspection pack with full post-Brexit divergence. By **MEOK AI Labs**.

## Why this exists

UK livestock haulage (~3,000 authorised operators) sits at the intersection of EU REG 1/2005 (retained UK law), APHA roadside enforcement, Defra's restated 1 December 2024 guidance, and the Windsor Framework SPS checks at Sealogue for GB->NI movements.

Real cases this MCP exists to prevent:

- **Cheale Meats Ltd (2023)** — multiple Animal Welfare Act + REG 1/2005 prosecutions led to operator **licence revocation** (out of business).
- **Onley Manor Farm v APHA (2022)** — confirmed the 8-hour boundary bites the moment crossed, even by 30 minutes. Type 2 authorisation, GPS, journey log all become mandatory.
- **1 Dec 2024 onwards** — APHA issued ~£250k of monetary penalties + 38 transporter authorisations suspended.

This MCP is the callable compliance layer above APHA spreadsheets, TRACES NT, and Defra's Schemes of Inspection.

## Install

```bash
pip install meok-livestock-welfare-transport-mcp
```

## Tools (7)

| Tool | Use case |
|------|----------|
| `check_journey_log_long_journey` | EU 1/2005 Annex II log + GPS for >8h journeys |
| `check_transporter_authorisation` | Type 1 (short <8h) vs Type 2 (long >8h) — Onley Manor precedent |
| `check_driver_competence_certificate` | CofC mandatory >65km, species endorsement |
| `check_vehicle_approval_livestock` | Species-specific vehicle approval (cattle/sheep/pigs/poultry/horses) |
| `check_loading_density_species` | Annex I Chapter VII loading densities |
| `check_rest_water_feed_journey` | Drive/rest cadence + temperature welfare range |
| `prepare_apha_inspection_pack` | APHA roadside prep + 1 Dec 2024 UK Brexit divergence flags |

## Pricing

- **Free** — MIT self-host
- **Starter** — £79/mo (1 operator, basic checks)
- **Pro** — £249/mo (multi-vehicle, journey logs, APHA pack)
- **Fleet** — £999/mo (>50 vehicles, multi-species, SSO, abattoir API)

## Regulatory basis

- EU Regulation (EC) 1/2005 — Welfare of Animals during Transport (retained UK law)
- Welfare of Animals (Transport) (England) Order 2006 SI 2006/3260 + sister SIs (Wales 2007/1047, Scotland SSI 2006/606, NI 2006/441)
- Animal Welfare Act 2006 — s.4 unnecessary suffering offence
- Animal Welfare (Livestock Exports) Act 2024 — slaughter/fattening export ban
- APHA Code of Practice for Animal Transport (current revision)
- EFSA AHAW Scientific Opinion 2022
- WOAH/OIE Terrestrial Code Chapter 7.3
- Windsor Framework + TCA Annex SPS-2 (GB <-> NI <-> EU)

## Buy Pro

Pro tier (£249/mo) and Fleet (£999/mo): <https://www.csoai.org/checkout>


## Configuration

Add to your `claude_desktop_config.json` (Claude Desktop) or your MCP client config:

```json
{
  "mcpServers": {
    "meok-livestock-welfare-transport-mcp": {
      "command": "uvx",
      "args": ["meok-livestock-welfare-transport-mcp"]
    }
  }
}
```

Or: `pip install meok-livestock-welfare-transport-mcp` then run the `meok-livestock-welfare-transport-mcp` command (stdio transport).

## Examples

Once configured, ask your assistant, for example:
- "Use `check_journey_log_long_journey` to …"
- "Use `check_transporter_authorisation` to …"
- "Use `check_driver_competence_certificate` to …"


<!-- GEO-FOOTER:v1 -->

---

### Part of the MEOK constellation

This MCP is one node in a connected ecosystem built by **MEOK AI LABS** around a single
sovereign AI core — governed agents with a hash-chained audit trail, mapped to the CSOAI
compliance charter.

- 🌐 The whole map: **<https://meok.ai/constellation>**
- 🛡️ AI governance & certification: **<https://councilof.ai>** · **<https://csoai.org>**
- ✅ Verify any signed report: **<https://meok.ai/verify>**
