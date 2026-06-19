## Cloudflare Certificates

### Summary

The SSL certificate for `gitlab.com` and `staging.gitlab.com` are provided by SSLMate. SSL certificates are downloaded from SSLMate and placed into a Vault Secret. We use a Custom SSL Certificate in Cloudflare which is managed using Terraform. Terraform retrieves the secret from Vault and uploads the corresponding certificate to Cloudflare.

### Certificate Authority Changes

Sectigo is the Certificate Authority of the SSLMate certificates for `gitlab.com` and `staging.gitlab.com`. In the future we plan to go back to using [Cloudflare's Advanced Certificate Manager](https://developers.cloudflare.com/ssl/edge-certificates/advanced-certificate-manager/) and enable Cloudflare [Total TLS](https://developers.cloudflare.com/ssl/edge-certificates/additional-options/total-tls/), which will require updating the Certificate Authority to a supported [Cloudflare Supported CA](https://developers.cloudflare.com/ssl/reference/certificate-authorities/) which as of now are either Let's Encrypt or Google Trust Services.

Changing the Certificate Authority of our Edge SSL certificates have caused problems in the past with services like Private Hosted Runners, AWS OIDC, and customer legacy CI images. See related incidents [7012](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/7012) and [17265](https://gitlab.com/gitlab-com/gl-infra/production/-/issues/17265).

When updating the Certificate Authority of our Edge SSL Certificates, a [C1 Change Request](https://handbook.gitlab.com/handbook/engineering/infrastructure-platforms/change-management/#criticality-1) has been opened and approved.
The Change Request, should include the following:

- Steps for notifying customers of the upcoming change to allow them be prepared ahead of time. We should aim for notifying them at least 2-4 weeks in advance.
- Steps for notifying Support of upcoming change.
- A timeline of the changes.

### SSLMate

We order SSL certificates using SSLMate. You can download the certificate chain for each domain at the links below:

- [staging.gitlab.com](https://certs.sslmate.com/hZB2otKrJ6blWJSr3wGt/staging.gitlab.com.chained.pem)
- [gitlab.com](https://certs.sslmate.com/KpmMJ4SA2OIM0ELtUAGo/gitlab.com.chained.pem)

These SSL certificates can be accessed without authenticating to the SSLMate Console.

### Vault Secrets

The private key and certificate chain for these certificates are stored in Vault:

- [staging.gitlab.com](https://vault.gitlab.net/ui/vault/secrets/ci/kv/ops-gitlab-net%2Fgitlab-com%2Fgl-infra%2Fconfig-mgmt%2Fcloudflare-custom-certs%2Fstaging-gitlab-com/details?version=1)
- [gitlab.com](https://vault.gitlab.net/ui/vault/secrets/ci/kv/ops-gitlab-net%2Fgitlab-com%2Fgl-infra%2Fconfig-mgmt%2Fcloudflare-custom-certs%2Fgitlab-com/details?version=1)

### Cloudflare Terraform Configuration

Our `Cloudflare Edge Certificates` can be found here:

- [staging.gitlab.com](https://dash.cloudflare.com/852e9d53d0f8adbd9205389356f2303d/staging.gitlab.com/ssl-tls/edge-certificates)
- [gitlab.com](https://dash.cloudflare.com/852e9d53d0f8adbd9205389356f2303d/gitlab.com/ssl-tls/edge-certificates)

These are all managed by Terraform
[here](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/blob/main/environments/cloudflare-custom-certs/certificates.tf).

### SSL Certificate Rotation

#### Certificates Updater

Our [Certificates-Updater Tool](https://gitlab.com/gitlab-com/gl-infra/certificates-updater) will automatically check if the custom certificates in Vault are close to expiry, and renew them if they are. This project has a scheduled pipeline that's executed twice a week.

Edge SSL Certificates are updated in Cloudflare by the `Automatic apply for Cloudflare custom certs environment` [Terraform scheduled pipeline](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/pipeline_schedules). This pipeline is scheduled to run automatically from Mon-Fri at 10:30AM UTC.

#### Manual Renewal

If a certificate needs to be updated manually, follow these steps to update the Cloudflare Edge Certificates:

1. Download the new certificate chain from the [links provided above](#sslmate).

    - staging.gitlab.com:

    ```
    wget https://certs.sslmate.com/hZB2otKrJ6blWJSr3wGt/staging.gitlab.com.chained.pem
    ```

      - gitlab.com:

    ```
    wget https://certs.sslmate.com/KpmMJ4SA2OIM0ELtUAGo/gitlab.com.chained.pem
    ```

2. Upload certificate chain to Vault:

    - staging.gitlab.com

    ```
    export MOUNT=ci
    export PATH=ops-gitlab-net/gitlab-com/gl-infra/config-mgmt/cloudflare-custom-certs/staging-gitlab-com
    cat staging.gitlab.com.chained.pem | vault kv patch -mount=$MOUNT $PATH certificate_chain=-
    ```

    - gitlab.com

    ```
    export MOUNT=ci
    export PATH=ops-gitlab-net/gitlab-com/gl-infra/config-mgmt/cloudflare-custom-certs/gitlab-com
    cat gitlab.com.chained.pem | vault kv patch -mount=$MOUNT $PATH certificate_chain=-
    ```

3. Update secret in Cloudflare by running the `Automatic apply for Cloudflare custom certs environment` [Terraform scheduled pipeline](https://ops.gitlab.net/gitlab-com/gl-infra/config-mgmt/-/pipeline_schedules).
