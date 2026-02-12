# GitHub Actions Secrets Configuration

This document lists all the secrets required for the CI/CD workflows to function properly.

## Required Secrets

### GitHub Token (Automatic)

| Secret | Description | Required For |
|--------|-------------|--------------|
| `GITHUB_TOKEN` | Automatically provided by GitHub Actions | Container registry login, deployments |

### Code Quality & Coverage

| Secret | Description | Required For | How to Obtain |
|--------|-------------|--------------|---------------|
| `SONAR_TOKEN` | SonarQube/SonarCloud authentication token | CI - Security scan | [SonarCloud Security](https://sonarcloud.io/account/security) or your SonarQube instance |
| `SONAR_HOST_URL` | SonarQube server URL (omit for SonarCloud) | CI - Security scan | Your SonarQube server (e.g., `https://sonarqube.example.com`) |
| `CODECOV_TOKEN` | Codecov.io upload token | CI - Test coverage upload | [Codecov Dashboard](https://codecov.io/) |

### Kubernetes Credentials

| Secret | Description | Required For | How to Generate |
|--------|-------------|--------------|------------------|
| `KUBE_CONFIG_DEV` | Base64-encoded kubeconfig for dev cluster | CD-Dev | `cat ~/.kube/config \| base64` |
| `KUBE_CONFIG_STAGING` | Base64-encoded kubeconfig for staging cluster | CD-Staging | `cat ~/.kube/config \| base64` |
| `KUBE_CONFIG_PROD` | Base64-encoded kubeconfig for production cluster | CD-Production | `cat ~/.kube/config \| base64` |

> **Note:** For cloud providers, use service account credentials with minimal required permissions:
> - **AWS EKS:** Create an IAM user with EKS access, use `aws eks update-kubeconfig`
> - **GKE:** Use `gcloud container clusters get-credentials`
> - **AKS:** Use `az aks get-credentials`

### LLM Provider API Keys

| Secret | Description | Required For | How to Obtain |
|--------|-------------|--------------|---------------|
| `ANTHROPIC_API_KEY` | Anthropic Claude API key | CI tests, CD deployments | [Anthropic Console](https://console.anthropic.com/) |
| `OPENAI_API_KEY` | OpenAI API key | CI tests, CD deployments | [OpenAI Platform](https://platform.openai.com/api-keys) |

### Redis (Staging)

| Secret | Description | Required For |
|--------|-------------|--------------|
| `STAGING_REDIS_URL` | Redis connection URL for staging | CD-Staging integration tests |

### Notifications

| Secret | Description | Required For | How to Obtain |
|--------|-------------|--------------|---------------|
| `SLACK_WEBHOOK` | Slack incoming webhook URL | All CD workflows (notifications) | [Slack Incoming Webhooks](https://api.slack.com/messaging/webhooks) |

## Setting Up Secrets

### Via GitHub UI

1. Navigate to your repository on GitHub
2. Go to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Enter the secret name and value

### Via GitHub CLI

```bash
# Set a secret
gh secret set SECRET_NAME --body "secret_value"

# Set from file
gh secret set KUBE_CONFIG_DEV < kubeconfig-dev.txt

# Set base64-encoded kubeconfig
cat ~/.kube/config | base64 | gh secret set KUBE_CONFIG_DEV
```

## Environment Protection Rules

For production deployments, configure environment protection rules:

1. Navigate to **Settings** → **Environments**
2. Create environment: `production`
3. Enable **Required reviewers** and add approvers
4. (Optional) Enable **Wait timer** for deployment delay
5. (Optional) Add **Deployment branches** restriction to `main` only

### Recommended Environment Settings

| Environment | Required Reviewers | Wait Timer | Branch Restriction |
|-------------|-------------------|------------|-------------------|
| development | No | None | `develop` |
| staging | Optional | None | `main` |
| production | **Yes (2 reviewers)** | 5 minutes | `main` (tags only) |

## Validating Secrets

To verify secrets are correctly configured without exposing them:

```yaml
- name: Verify secrets are set
  run: |
    if [ -z "${{ secrets.KUBE_CONFIG_DEV }}" ]; then
      echo "ERROR: KUBE_CONFIG_DEV is not set"
      exit 1
    fi
    echo "✅ All required secrets are configured"
```

## Security Best Practices

1. **Rotate secrets regularly** - especially API keys and kubeconfigs
2. **Use short-lived credentials** when possible (e.g., OIDC with cloud providers)
3. **Limit secret scope** - use environment-specific secrets
4. **Audit secret access** - review Actions logs for secret usage
5. **Never log secrets** - GitHub automatically masks them, but be careful with base64
