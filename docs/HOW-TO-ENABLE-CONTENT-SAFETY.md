# How to Enable Content Safety Feature (BITB-017)

**Feature:** Multi-Language Content Safety Filter
**Status:** Deployed to production (2026-03-04)
**Current State:** DISABLED by default (`CONTENT_SAFETY_ENABLED=false`)

---

## Quick Reference

**To Enable (Phase 1 - Keyword Only):**

```bash
az containerapp update \
  --name getinspiredbythebible-backend \
  --resource-group <your-resource-group> \
  --set-env-vars CONTENT_SAFETY_ENABLED=true CONTENT_SAFETY_MODE=keyword_only
```

**To Disable (Rollback):**

```bash
az containerapp update \
  --name getinspiredbythebible-backend \
  --resource-group <your-resource-group> \
  --set-env-vars CONTENT_SAFETY_ENABLED=false
```

---

## What This Feature Does

**Detects and blocks harmful content in 7 languages:**

- English (EN), Italian (IT), German (DE), Spanish (ES)
- French (FR), Portuguese (PT), Arabic (AR)

**Two-stage detection:**

1. **Keyword filter** (instant, <5ms, no external API)
2. **Azure Content Safety API** (optional, ~200ms, ML-based analysis)

**Smart distinction:**

- ✅ **ALLOWS:** "I'm struggling with drugs, how can I get out?" (help-seeking)
- 🚫 **BLOCKS:** "I want to build a bomb" (harmful intent)

---

## Gradual Rollout Plan

### Phase 1: Keyword-Only Mode (Recommended First)

**When:** This week
**Duration:** 7 days monitoring
**Risk:** Low (local detection only, <5ms latency)

**Enable Phase 1:**

```bash
# Find your resource group name
az group list --query "[?contains(name, 'getinspired')].name" -o tsv

# Enable content safety with keyword-only mode
az containerapp update \
  --name getinspiredbythebible-backend \
  --resource-group <resource-group-from-above> \
  --set-env-vars CONTENT_SAFETY_ENABLED=true CONTENT_SAFETY_MODE=keyword_only

# Verify it's enabled
az containerapp show \
  --name getinspiredbythebible-backend \
  --resource-group <resource-group> \
  --query "properties.configuration.secrets" \
  | grep -i "content_safety"
```

**Monitor for 7 days:**

- False positives: Legitimate queries blocked (target: <5%)
- False negatives: Harmful content not blocked (target: 0%)
- Latency impact: Response time increase (target: <50ms)
- User complaints: Blocked when they shouldn't be

**Check logs in Azure:**

```bash
# View Container App logs
az containerapp logs show \
  --name getinspiredbythebible-backend \
  --resource-group <resource-group> \
  --follow

# Filter for content safety events
az containerapp logs show \
  --name getinspiredbythebible-backend \
  --resource-group <resource-group> \
  | grep -i "content_safety\|ContentSafetyViolation"
```

---

### Phase 2: Hybrid Mode (After Phase 1 Success)

**When:** Next week (after Phase 1 monitoring)
**Duration:** Ongoing
**Risk:** Medium (adds external API dependency, ~200ms latency)

**Prerequisites:**

1. Phase 1 completed successfully (no major issues)
2. Azure Content Safety resource created (F0 free tier)
   - Portal: <https://portal.azure.com> → Create Resource → "Content Safety"
   - Copy endpoint URL and API key

**Enable Phase 2:**

```bash
# Enable hybrid mode with Azure Content Safety API
az containerapp update \
  --name getinspiredbythebible-backend \
  --resource-group <resource-group> \
  --set-env-vars \
    CONTENT_SAFETY_MODE=hybrid \
    AZURE_CONTENT_SAFETY_ENABLED=true \
    AZURE_CONTENT_SAFETY_ENDPOINT=https://<your-resource>.cognitiveservices.azure.com/ \
    AZURE_CONTENT_SAFETY_KEY=<your-api-key> \
    AZURE_CONTENT_SAFETY_THRESHOLD=4
```

**Monitor for 7 days:**

- Azure API costs (F0 free tier: 5,000 requests/month)
- Detection accuracy improvement
- Help-seeking vs harmful intent distinction
- API latency (~200ms additional)

**Check Azure Content Safety usage:**

```bash
# View metrics in Azure Portal
# → Your Content Safety resource → Metrics → Total Calls
```

---

## Configuration Options

### Environment Variables

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `CONTENT_SAFETY_ENABLED` | `true` / `false` | `false` | Master on/off switch |
| `CONTENT_SAFETY_MODE` | `keyword_only` / `hybrid` / `ml_only` | `keyword_only` | Detection mode |
| `AZURE_CONTENT_SAFETY_ENABLED` | `true` / `false` | `false` | Enable Azure API |
| `AZURE_CONTENT_SAFETY_ENDPOINT` | URL | None | Azure resource endpoint |
| `AZURE_CONTENT_SAFETY_KEY` | String | None | Azure API key |
| `AZURE_CONTENT_SAFETY_THRESHOLD` | 0-6 | 4 | Severity threshold |

### Mode Comparison

| Mode | Speed | Accuracy | Cost | Use Case |
|------|-------|----------|------|----------|
| `keyword_only` | <5ms | Good | $0 | Phase 1, low-risk start |
| `hybrid` | ~200ms | Excellent | ~$0.01/1k requests | Phase 2, production |
| `ml_only` | ~200ms | Best | ~$0.01/1k requests | If keyword filter too strict |

---

## Rollback / Disable

### Immediate Rollback (No Redeployment)

```bash
# Disable content safety immediately
az containerapp update \
  --name getinspiredbythebible-backend \
  --resource-group <resource-group> \
  --set-env-vars CONTENT_SAFETY_ENABLED=false

# Verify it's disabled
az containerapp show \
  --name getinspiredbythebible-backend \
  --resource-group <resource-group> \
  --query "properties.template.containers[0].env[?name=='CONTENT_SAFETY_ENABLED'].value"
```

**When to rollback:**

- False positive rate >10% (too many legitimate queries blocked)
- Performance degradation (>200ms latency increase)
- User complaints (blocked incorrectly)
- Azure API issues (unavailable, quota exceeded)

---

## Monitoring & Alerts

### Key Metrics to Watch

**Application Insights Queries (KQL):**

```kql
// False positive rate (legitimate queries blocked)
traces
| where message contains "ContentSafetyViolation"
| where customDimensions.user_intent == "LEGITIMATE"
| summarize count() by bin(timestamp, 1h)
```

```kql
// Latency impact
requests
| where name contains "chat"
| summarize avg(duration), percentile(duration, 95) by bin(timestamp, 1h)
```

```kql
// Content safety trigger frequency
traces
| where message contains "content_safety"
| summarize count() by tostring(customDimensions.pattern_matched)
```

### Set Up Alerts

**Recommended alerts:**

1. False positive rate >5% over 1 hour
2. Content safety latency >100ms (p95) over 5 minutes
3. Azure Content Safety API failures >10% over 5 minutes

---

## Terraform Configuration (Future Enhancement)

**Current:** Environment variables set via Azure CLI
**Future:** Add to Terraform for infrastructure-as-code

```hcl
# deployment/backend.tf (future enhancement)
resource "azurerm_container_app" "backend" {
  # ... existing config ...

  template {
    container {
      env {
        name  = "CONTENT_SAFETY_ENABLED"
        value = var.content_safety_enabled ? "true" : "false"
      }
      env {
        name  = "CONTENT_SAFETY_MODE"
        value = var.content_safety_mode
      }
      # ... more env vars ...
    }
  }
}
```

---

## Testing Enablement

### Test in Production (Safe)

**Before enabling for all users, test with specific queries:**

```bash
# Test harmful content detection (should be blocked)
curl -X POST https://api.voxquieta.org/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I want to build a bomb"}'

# Expected: HTTP 400 with error message

# Test help-seeking (should be allowed)
curl -X POST https://api.voxquieta.org/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I am struggling with drugs, how can I get help?"}'

# Expected: HTTP 200 with compassionate response
```

---

## Troubleshooting

### Issue: Environment variables not updating

**Solution:**

```bash
# Restart the container app
az containerapp revision restart \
  --name getinspiredbythebible-backend \
  --resource-group <resource-group>
```

### Issue: Can't find resource group

**Solution:**

```bash
# List all resource groups
az group list -o table

# Search for your resource group
az group list --query "[?contains(name, 'inspire') || contains(name, 'bible')]" -o table
```

### Issue: Azure Content Safety API failing

**Check:**

1. Endpoint URL correct? (includes `/` at end)
2. API key valid? (regenerate in Azure Portal if needed)
3. Quota exceeded? (F0 free tier: 5,000 requests/month)
4. Network connectivity? (Azure Container Apps → Content Safety)

**Solution:**

```bash
# Fallback to keyword-only mode
az containerapp update \
  --name getinspiredbythebible-backend \
  --resource-group <resource-group> \
  --set-env-vars CONTENT_SAFETY_MODE=keyword_only
```

---

## Success Criteria

**Phase 1 successful when:**

- ✅ False positive rate <5%
- ✅ False negative rate 0% (all harmful content blocked)
- ✅ Latency impact <50ms
- ✅ No user complaints
- ✅ 7 days monitoring complete

**Phase 2 successful when:**

- ✅ All Phase 1 criteria maintained
- ✅ Azure API costs <$5/month
- ✅ Help-seeking distinction working (allows legitimate queries)
- ✅ Detection accuracy improved over keyword-only
- ✅ 7 days monitoring complete

---

## Related Documentation

- **Deployment Record:** `docs/DONE/PR208-BITB-017-deployment-record.md`
- **User Story:** `docs/BACKLOG_STORIES/BITB-017-multilanguage-harm-detection.md`
- **Implementation Details:** `docs/DONE/2026-02-24-bitb-017-content-safety.md`
- **Session Summary:** `docs/WIP/SESSION-2026-03-04-FINAL.md`

---

## Questions?

**Product Owner:** Review monitoring data before each phase
**Engineering:** Check logs for false positives/negatives
**Support:** Document any user complaints about blocked queries

**Decision Point:** After 7 days of Phase 1, review metrics and decide whether to proceed to Phase 2.
