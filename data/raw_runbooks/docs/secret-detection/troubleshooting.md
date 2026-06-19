# Secret Detection Partner Token Verification Troubleshooting

## Overview

This runbook covers troubleshooting for the Secret Detection partner token verification system.

## Metrics Dashboard

[Secret Detection Partner Token Verification Dashboard](https://dashboards.gitlab.net/goto/cf3zed4vmgo3ke?orgId=1)

## Common Alerts

### SecretDetectionPartnerAPIHighErrorRate

**Severity: S3**

High error rate (>10%) when verifying tokens with partner APIs.

#### Investigation Steps

1. Check the dashboard to identify which partner is failing
2. Review error breakdown by `error_type`:

   * `network_error`: Connectivity issues
   * `rate_limit`: Rate limit exceeded
   * `response_error`: Invalid/unparseable responses
3. Check recent deployments or configuration changes
4. Review partner-specific status pages, example:

   * AWS: [https://status.aws.amazon.com](https://status.aws.amazon.com)
   * GCP: [https://status.cloud.google.com](https://status.cloud.google.com)
   * Postman: [https://status.postman.com](https://status.postman.com)

#### Resolution

1. **Temporary (< 1 hour):** If partner has known incident, wait for recovery

2. **Disable partner (1–24 hours):** Edit `ee/lib/security/secret_detection/partner_tokens/registry.rb`

   ```ruby
   'AWS' => {
     client_class: ::Security::SecretDetection::PartnerTokens::AwsClient,
     rate_limit_key: :partner_aws_api,
     enabled: false  # ← Set to false
   }
   ```

---

### SecretDetectionPartnerAPIHighLatency

**Severity: S3**

P95 latency exceeds 5 seconds for partner API calls.

#### Investigation Steps

1. Check if it's systemic or partner-specific in dashboard
2. Review partner status pages (may show degraded performance)
3. Look for regional issues (AWS/GCP might have region-specific problems)

#### Resolution

1. **Temporary (< 6 hours):** If P95 < 10s, monitor — partners are slow but functional

2. **Increase timeout (6–24 hours):** Edit [base_client.rb](https://gitlab.com/gitlab-org/gitlab/-/blob/039f53044c4bdc1ab27ccc14c3b1f1f9876f2d08/ee/lib/security/secret_detection/partner_tokens/base_client.rb)

   ```ruby
   DEFAULT_TIMEOUT = 10.seconds  # Was 5.seconds
   ```

3. **Disable partner (> 24 hours):** Set `enabled: false` in Registry (see above)

4. **Post-incident:** File issue to investigate why partner is consistently slow

---

### SecretDetectionPartnerAPIRateLimitHit

**Severity: S4**

Rate limits are being hit (>0.1 req/s sustained for 5 minutes).

#### Investigation Steps

1. Check dashboard for which partner is hitting limits

2. Verify current rate limit settings in [application_rate_limiter.rb](https://gitlab.com/gitlab-org/gitlab/-/blob/039f53044c4bdc1ab27ccc14c3b1f1f9876f2d08/ee/lib/ee/gitlab/application_rate_limiter.rb)

   ```ruby
   partner_aws_api: { threshold: -> { 400 }, interval: 1.second }
   partner_gcp_api: { threshold: -> { 500 }, interval: 1.second }
   partner_postman_api: { threshold: -> { 4 }, interval: 1.second }
   ```

3. Check Sidekiq queue depth: `Sidekiq::Queue.new('security_secret_detection_partner_token_verification').size` using [teleport](https://gitlab.com/gitlab-com/runbooks/-/blob/master/docs/teleport/Connect_to_Rails_Console_via_Teleport.md).

4. Look for burst traffic patterns (large pipeline, multiple projects)

#### Resolution

1. **Normal operation:** Some rate limiting is expected with Postman (4 req/s). If < 100/hour, no action needed
2. **High traffic burst:** Queue will self-regulate with exponential backoff. Monitor queue depth:

   * If queue < 10k jobs: Normal, will clear in ~1 hour
   * If queue > 50k jobs: Consider temporarily disabling partner
3. **Persistent issue:** Partner may have changed rate limits. Check their API docs and update `application_rate_limiter.rb`
4. **Last resort:** Disable partner, process queue, re-enable with lower rate limits

---

### SecretDetectionPartnerAPINetworkErrors

**Severity: S3**

Network connectivity issues to partner APIs (>0.5 errors/sec).

#### Investigation Steps

1. Check dashboard to identify affected partner(s)

2. Verify GitLab.com can reach partner APIs from console using [teleport](https://gitlab.com/gitlab-com/runbooks/-/blob/master/docs/teleport/Connect_to_Rails_Console_via_Teleport.md):

   ```ruby
   # Run in Rails console
   uri = URI('https://sts.amazonaws.com')
   Net::HTTP.get_response(uri)
   ```

3. Check for firewall/networking changes in #infrastructure

4. Look for DNS issues: `dig sts.amazonaws.com` from GitLab runners

5. Review recent SSL certificate renewals

#### Resolution

1. **Single partner affected:** Likely partner-side issue. Disable partner (see above), monitor partner status page
2. **Multiple partners affected:** Likely GitLab network issue

   * Check with SRE team in #production
   * Review recent network changes
   * Verify egress rules haven't changed
3. **SSL/TLS errors:** Check certificate validity, may need to update CA bundle
4. **Temporary workaround:** Disable affected partners until network issue resolved

---

## Manual Verification

If you need to manually verify a specific token in development or using using [teleport](https://gitlab.com/gitlab-com/runbooks/-/blob/master/docs/teleport/Connect_to_Rails_Console_via_Teleport.md):

```ruby
# Rails console
finding = Vulnerabilities::Finding.find(FINDING_ID)
token_type = finding.identifiers.find { |i| i['external_type'] == 'gitleaks_rule_id' }&.dig('external_id')

# Get partner name from token_type
partner_config = Security::SecretDetection::PartnerTokens::Registry.partner_for(token_type)

# Verify token
client = partner_config[:client_class].new
result = client.verify_token(finding.metadata['raw_source_code_extract'])

puts "Valid: #{result.valid}, Metadata: #{result.metadata}"
```

---

## Escalation

* Team: Secret Detection (@gitlab-org/secure/secret-detection)
* Slack: #g_ast-secret-detection
