# Email-based One Time Passwords (OTP)

## Summary

Email-based OTP is a mandatory authentication feature for GitLab.com users signing in with passwords. Users receive a code via email during login and must enter it to proceed. This runbook helps SREs triage and mitigate Email OTP-related incidents.

Development docs: <https://docs.gitlab.com/development/email_one_time_passwords>.

### Similar features

It's similar to [Two-factor authentication](https://docs.gitlab.com/user/profile/account/two_factor_authentication) but with key differences:

- **Mandatory rollout**: All GitLab.com users signing in with passwords will be required to use Email OTP[^rollout-issue]
- **Exceptions**: Email OTP is unavailable when:
  - Group policy requires other two-factor authentication methods
  - Account uses an external identity provider
  - Account is scheduled for automatic enablement at a future date[^enable-otp]

It is also similar to
[Email OTP for account email verification](https://docs.gitlab.com/security/email_verification/),
which will lock an account and require an emailed code when potential abuse is
detected.

## Escalation

Depending on the urgency required for technical assistance, the
escalation path is:

1. @ mentioning `@gitlab-com/gl-security/product-security/product-security-engineering`
1. Ask in [`#mfa_default_planning`](https://gitlab.enterprise.slack.com/archives/C08GXLZKXHV)
1. Ask in [`#g_sscs_authentication`](https://gitlab.enterprise.slack.com/archives/CLM1D8QR0)
1. Page the Authentication team using Pager Duty. (Product Security Engineering is not in Pager Duty).

### Known & Documented Impacts

- **Password-based API authentication blocked**: `git clone` and `docker login` will fail with `Access denied`[^access-denied] when a password is used.
- **Mandatory code entry**: Once enforcement begins, users must enter the emailed code to sign in.[^email-otp-docs]

Support has an [existing 2FA removal workflow](https://handbook.gitlab.com/handbook/support/workflows/2fa-removal/) to help users who cannot access their email.

## Troubleshooting

### Symptom: Users cannot sign in

#### Cause A: Code error in authentication flow

Look for errors in:

- `VerifiesWithEmail` (`app/controllers/concerns/verifies_with_email.rb`),
- `Users::EmailVerification::GenerateTokenService`, or
- `Users::EmailVerification::ValidateTokenService`

**Solution:**

1. Confirm the issue is Email OTP-related
2. Follow **Global temporary hold**
3. Notify `#mfa_default_planning` for developer investigation

### Symptom: Email OTP emails not being delivered

#### Cause A: Mailgun outage

Email OTP depends on Mailgun for email delivery.

**Solution:**

1. Check the [Mailgun Service runbooks](https://gitlab.com/gitlab-com/runbooks/-/blob/master/docs/mailgun/README.md)
2. If Mailgun cannot fix it, follow **Global temporary hold**

#### Cause B: User error or spam filters

The email was delivered but the user cannot find it.

**Solution:**

1. Direct user to [GitLab Support](https://about.gitlab.com/support/).
   Support has an
   [existing 2FA removal workflow](https://handbook.gitlab.com/handbook/support/workflows/2fa-removal/)
   to help users who cannot access their email.

### Symptom: Users cannot be created or updated

#### Cause A: Code error in user enrollment

Look for errors in:

- `Users::BuildService` (new user enrollment)
- `Users::UpdateService`, or
- `Users::EmailOtpEnrollment`

**Solution:**

1. Confirm the issue is Email OTP-related
2. If it affects existing and new users, follow **Global temporary hold**
2. If it only affects new users, follow **Disable for new users**
3. Notify `#mfa_default_planning` for developer investigation

## Mitigation Steps

### Delaying or disabling for specific users

**What:** Un-enroll user(s) from Email OTP. They won't see the prompt and password-based APIs will work again.

**When:**

- User is locked out (no access to email inboxes)
- Customer impacted by blocked password-based APIs

**Approval:** Incident Manager On Call (IMOC)

**Who can execute:** SREs with Rails Console Write privileges

**How:**

1. Gather affected user ID(s)
2. Engage an SRE to execute:

```ruby
# To delay enrollment
some_future_date = Time.parse('YYYY-MM-DDTHH:MM:SSZ')
user.update(email_otp_required_after: some_future_date)
# or for multiple users
users.update_all(email_otp_required_after: some_future_date)
```

3. Document the action on the incident/support ticket
4. Notify `#mfa_default_planning` for awareness

**Knock-on impacts:**

- If delayed: No further action needed
- If disabled with `require_minimum_email_based_otp_for_users_with_passwords` enabled: User(s) re-enrolled automatically on next sign-in
- If disabled with flag disabled: User(s) need to be added to a later cohort

**FAQ:**

*Q: Why can't we disable the feature flag per user?*

Phase 1 sets `email_based_mfa` to true for all users. GitLab feature flags don't support "except user X" exceptions[^feature-flags]. User-specific flags also aren't designed for hundreds/thousands of actors.

*Q: Can users self-service this?*

Only if `require_minimum_email_based_otp_for_users_with_passwords` is disabled. Otherwise, they must enable App-based TOTP or WebAuthn first.

*Q: The user is still being asked to enter a code?*

That may be due to an existing feature,
[email OTP for account email verification](https://docs.gitlab.com/security/email_verification/),
which is not controlled by the Feature Flag or `email_otp_required_after`
attribute.

### Global temporary hold

**What:** Disable Email OTP for all users temporarily. Users won't see the prompt, password-based APIs revert to being unblocked, and the Email OTP preference disappears from UI. (New users will still be automatically enrolled behind the scenes, but they won't see the feature).

**When:** High/critical impact affecting many/most users

**Approval:** Incident Manager On Call (IMOC)

**Who can execute:** Anyone with ChatOps privileges (most developers, all SREs)

**How:**

1. In Slack, go to `#production`
2. (Optional) Verify current state: `/chatops gitlab run feature get email_based_mfa`
3. Disable: `/chatops gitlab run feature set email_based_mfa false`
4. Notify `#mfa_default_planning`

**Knock-on impacts:**

- Must decide when/if to re-enable
- Credential stuffing attacks possible while disabled

**FAQ:**

*Q: Users are still being asked to enter a code?*

That may be due to an existing feature,
[email OTP for account email verification](https://docs.gitlab.com/security/email_verification/),
which is not controlled by the Feature Flag or `email_otp_required_after`
attribute.

### Disable for new users

**What:** Disable Email OTP enrollment for new users users temporarily.
New users could still find their way to the User Preference and enable
Email-based OTP manually.

**When:** New users can't sign up

**Approval:** Incident Manager On Call (IMOC)

**Who can execute:** Anyone with ChatOps privileges (most developers, all SREs)

**How:**

1. Validate that `Gitlab::CurrentSettings.require_minimum_email_based_otp_for_users_with_passwords`
   is `false`. Otherwise, follow "Make Email OTP optional".
1. In Slack, go to `#production`
1. (Optional) Verify current state: `/chatops gitlab run feature get enrol_new_users_in_email_otp`
1. Disable: `/chatops gitlab run feature set enrol_new_users_in_email_otp false`
1. Notify `#mfa_default_planning`

**Knock-on impacts:**

- Must decide when/if to re-enable
- Must decide when/if to enforce Email OTP for users who signed up
  while `enrol_new_users_in_email_otp` was disabled.

### Make Email OTP optional

**What:** Remove the mandatory enforcement of Email OTP, without
changing existing enrollment in Email OTP.

**When:** The feature works, but we want to allow users to be able
to opt-out. (See also "Disable for new users").

**Approval:**

- If part of enacting "Disable for new users", then Incident Manager On Call (IMOC).
- Otherwise, VP of Product Security.

**How:**

1. Set `Gitlab::CurrentSettings.require_minimum_email_based_otp_for_users_with_passwords`
   to `false`
2. Notify `#mfa_default_planning`

### Full rollback

**What:** Remove the feature entirely from the codebase.

**When:** Feature doesn't work and rollout must be cancelled

**Approval:** E-Group

**Who can execute:** Release Manager + developer

**How:**

1. Execute **Global temporary hold**
2. Developers create revert MRs to:
   - Remove Email OTP database columns
   - Revert feature introduction MRs

**Knock-on impacts:** Removes feature from self-managed installations (was behind feature flag anyway)

[^rollout-issue]: <https://gitlab.com/gitlab-org/gitlab/-/issues/566615>
[^enable-otp]: <https://docs.gitlab.com/user/profile/account/two_factor_authentication/#enable-email-otp>
[^access-denied]: See [Two Factor Authentication Troubleshooting docs](https://docs.gitlab.com/user/profile/account/two_factor_authentication_troubleshooting/#error-http-basic-access-denied-if-a-password-was-provided-for-git-authentication-). Users must switch to using a Personal Access Token ([1](https://gitlab.com/gitlab-org/gitlab/-/blob/7f14ebed2fa690bfd77a2c9a507da4a12706eba2/doc/topics/git/clone.md#L63), [2](https://gitlab.com/gitlab-org/gitlab/-/blob/7f14ebed2fa690bfd77a2c9a507da4a12706eba2/doc/user/packages/container_registry/authenticate_with_container_registry.md#L43-44))
[^email-otp-docs]: <https://docs.gitlab.com/user/profile/account/two_factor_authentication/#sign-in-with-email-otp>
[^feature-flags]: <https://docs.gitlab.com/development/feature_flags/controls/#selectively-disable-by-actor>
