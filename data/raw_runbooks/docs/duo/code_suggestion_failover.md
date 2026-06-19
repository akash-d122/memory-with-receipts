<!-- Permit linking to GitLab docs and issues -->
<!-- markdownlint-disable MD034 -->
# GitLab Code Suggestion Failover Solution

This page provides instructions for switching the LLM provider in case of an outage with the primary provider. It is intended for product and support engineers troubleshooting LLM provider outages affecting **gitlab.com** users.

---

---

## How to switch to backup for code generation

We use a [feature flag to switch which model and model provider](https://gitlab.com/gitlab-org/gitlab/-/blob/master/ee/lib/code_suggestions/prompts/code_generation/ai_gateway_messages.rb#L37) are active for code generation.

If the primary model provider experiences an outage, enable the feature flag by running the following command in the `#production` Slack channel:

```
/chatops gitlab run feature set incident_fail_over_generation_provider true
```

After the primary LLM provider is back online, we can change back to the primary model by running this command in the `#production` Slack channel to disable the feature flag:

```
/chatops gitlab run feature set incident_fail_over_generation_provider false
```

## How to switch to backup for code completion

We use a [feature flag to switch which model and model provider](https://gitlab.com/gitlab-org/gitlab/-/blob/master/ee/lib/code_suggestions/tasks/code_completion.rb#L38) are active for code completion.

We are using a [feature flag](https://gitlab.com/gitlab-org/gitlab/-/issues/501503) to control whether to enable the failover solution.

To enable failover solution in production when the primary LLM is down, send this to #production slack channel:

```
/chatops gitlab run feature set incident_fail_over_completion_provider true
```

Note: on failover mode, direct access is automatically forbidden and all Code Suggestion requests become indirect access. For more details about direct vs indirect access, please refer to [the documentation](https://docs.gitlab.com/ee/user/project/repository/code_suggestions/#direct-and-indirect-connections).

After the primary LLM provider is back online, we can disable the feature flag, so that we are switching back to the primary LLM provider:

```
/chatops gitlab run feature set incident_fail_over_completion_provider false
```

## How to verify

* Go to [Kibana](https://log.gprd.gitlab.net/app/home#/) Analytics -> Discover
* Select `pubsub-mlops-inf-gprd-*` as Data views from the top left
* For code generation, search for `json.jsonPayload.message: "Returning prompt from the registry"`:
  * You should see `json.jsonPayload.prompt_id: code_suggestions/generations/base` and `json.jsonPayload.prompt_version <version>`
    * You can also find the template file in [this folder](https://gitlab.com/gitlab-org/modelops/applied-ml/code-suggestions/ai-assist/-/tree/main/ai_gateway/prompts/definitions/code_suggestions/generations/base?ref_type=heads)
    * For example, if the version is 2.0.1, then the template file is `ai-assist/ai_gateway/prompts/definitions/code_suggestions/generations/base/2.0.1.yml`
    * In this file we can find the current model and model provider, for example, here we are using `claude-3-5-sonnet@20241022` provided by `vertex_ai`:

      ```
      model:
        name: claude-3-5-sonnet@20241022
        params:
         model_class_provider: litellm
         custom_llm_provider: vertex_ai
         temperature: 0.0
         max_tokens: 2_048
         max_retries: 1
      ```

* For code completion, search for `json.jsonPayload.message: "code completion input:"`, and then we can find the provider that is currently in use:
  * if you see `json.jsonPayload.model_provider: anthropic`, then we are using the failover model `claude-3-5-sonnet-20240620` provided by `anthropic`
  * if you see another value for `json.jsonPayload.model_provider`, then we are using a non-failover model
