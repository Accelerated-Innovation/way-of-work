# Proposed changes to the Way of Work document

Implementing the standard surfaced a few gaps. These are proposals for the team; the
tooling already behaves as described and can be changed in `.wow.toml` / `config.py`.

## 1. AI provider keys (add to §3)
> **MUST NOT** commit AI provider keys (OpenAI, Anthropic, Azure OpenAI, Google, etc.), in any repository, on any branch. Push protection is enforced org-wide and cannot be self-bypassed. A key that was ever pushed is rotated immediately. Prefer keyless authentication (Managed Identity / workload identity) where the provider supports it.

## 2. Release branches for the version bump (§2, §5)
§5 says to bump the version when promoting to `staging`, but `develop` is protected and promotions merge `develop` as-is. The tooling bumps on a short-lived `release/vX.Y.Z` branch merged into `develop` just before the promotion PR. Proposed addition to the §2 table:

| `release/vX.Y.Z` | Version bump before promotion to staging | — | Tech lead |

## 3. Work item ID format (§14 Q3)
Branch and PR checks accept `1234` or `KEY-1234`. Once the work-item system is chosen, set `work_item_pattern` and `work_item_url` centrally.

## 4. "Applied" migrations (§7)
The check treats any migration that exists on the base branch as applied, because `develop` deploys automatically. Proposed wording: "**MUST NOT** edit a migration once it is merged to `develop`."

## 5. Demo track (§14 Q1)
The promotion check assumes `demo` is promoted from `staging` and `prod` from `demo` (or a hotfix). If `prod` should also accept `staging`, change `[promotion]` in the config.
