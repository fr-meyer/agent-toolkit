---
name: korean-law-openapi-compliance
description: Use this skill when applying for, configuring, or using Korea Ministry of Government Legislation 국가법령정보/open.law.go.kr Open API credentials, LAW_OC/KOREAN_LAW_API_KEY secrets, or Korean law MCP servers such as chrisryugj/korean-law-mcp. It enforces compliant low-volume use, source attribution, no API-key leakage, local stdio preference, and careful handling of legal/tax reference data to avoid access restriction, approval cancellation, misuse, or accidental publication of altered legal information.
---

# Korean Law OpenAPI Compliance

## Purpose

Use Korea's 국가법령정보 / 법제처 Open API responsibly and safely, especially through Korean-law MCP tooling. Treat API output as official-source reference data, not as final legal/tax advice.

## Non-negotiable guardrails

1. **No secret leakage**
   - Store the API auth value only in a secret/env variable such as `LAW_OC` or `KOREAN_LAW_API_KEY`.
   - Do not write the full key into repositories, memory files, reports, tickets, screenshots, shell history, URLs, or chat.
   - Mask keys in logs as `OC=***` / `LAW_OC=***`.
   - Avoid hosted or remote MCP URLs containing `?oc=<key>`. Query-string keys can leak through logs, browser history, reverse proxies, and screenshots.

2. **Prefer local stdio MCP**
   - For `korean-law-mcp`, prefer a local stdio server using env secrets.
   - Do not expose HTTP mode unless the user explicitly requests it after a security review.
   - Do not run generic setup helpers that write third-party client config unless the destination files are reviewed first.

3. **Avoid excessive calls**
   - No tight loops, broad crawling, mirror-building, or bulk download of legal databases.
   - Reuse cached prior results where possible.
   - Batch conceptually, but serialize API calls and keep request volume low.
   - If more than ~20 live API calls are likely, pause and explain the scope/risk; ask before continuing.
   - On 429, access-denied, bot/verification, IP/domain mismatch, or repeated server errors: stop, record the error, and do not retry aggressively.

4. **Use data as reference material**
   - Cite 법제처/국가법령정보 or the source endpoint/document for legal text used in outputs.
   - Do not present API output as legal/tax advice by itself.
   - For material legal/tax decisions, verify against the original text and, when needed, the competent agency or a qualified professional.

5. **Do not alter legal information deceptively**
   - Never forge, modify, or re-label legal text as if it came from 법제처.
   - If summarizing, clearly mark it as a summary and preserve source attribution.
   - If translating, mark it as a translation and keep the Korean original/source reference available.

## API application guidance

When helping a user apply for an OC/API key:

- Use a meaningful, honest purpose statement. Blank or nonsense purpose text can lead to cancellation.
- If the work is broad legal research through an MCP, selecting broad categories or `전체선택` is acceptable when the purpose statement says the project may search 법령, 조약, 판례, 해석례, 조세심판례, terminology, and related legal information.
- If the form asks for a server IP, use the actual outbound IP of the runtime that will call the API. If it may change, tell the user there may be a management/reissue step later rather than promising frictionless edits.
- If there is no public website/domain, use the form's `도메인 없음` option if available.

Purpose text pattern:

```text
개인 연구 및 법령정보 확인을 위한 비영리 활용입니다. 개인용 로컬 MCP 도구에서 국가법령정보 OPEN API를 호출하여 대한민국 법령정보 전반(현행법령, 행정규칙, 자치법규, 조약, 판례, 헌재결정례, 법령해석례, 국세청 법령해석, 조세심판례, 법령용어 및 관련 법령정보)을 검색·확인하고, 세무·법령 검토를 보조하는 참고자료로 활용할 예정입니다. API 결과는 법제처 제공 참고자료로 사용하며, 법률·세무 자문을 자동으로 제공하거나 법령정보를 위조·변조하지 않습니다. 결과물에는 출처를 명시하고, 중요한 사안은 원문 및 소관기관 또는 전문가 확인을 병행합니다. 과도한 호출을 피하고 개인 내부 검토 목적으로만 사용합니다.
```

## `korean-law-mcp` setup policy

Preferred pattern:

```json
{
  "mcpServers": {
    "korean-law": {
      "command": "korean-law-mcp",
      "env": {
        "LAW_OC": "<stored as secret, not literal in repo>"
      }
    }
  }
}
```

Operational rules:

- Prefer installing from the current npm package so semver dependencies can resolve to patched versions, unless there is a specific reason to use a pinned audited lockfile.
- Do not use the public hosted endpoint for private workflows unless explicitly approved.
- Do not enable HTTP mode with broad binding/CORS for personal legal/tax work.
- Use the MCP for retrieval, citation verification, and research assistance; do not let it file taxes, submit forms, or produce final legal conclusions without human review.

## Before responding with Korean legal/tax conclusions

- State whether the conclusion is from live API retrieval, prior notes, or general reasoning.
- Include the relevant source name and citation/endpoint result when available.
- If API access failed or results are incomplete, say so plainly.
- For tax filings, mark uncertain treaty/classification points for professional confirmation.
