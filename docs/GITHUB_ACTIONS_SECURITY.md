# GitHub Actions Security: Workflow Logs and Sensitive Data

## Question: Can I Make Actions Logs Private in a Public Project?

**Short Answer**: No, GitHub Actions workflow logs in public repositories are **always public** by design. There is no setting to make them private.

**Long Answer**: GitHub's design philosophy for public repositories emphasizes transparency and openness for open-source collaboration. When workflows run in a public repository, the logs are publicly accessible to anyone, regardless of whether they are logged into GitHub or not. This is an intentional design decision that cannot be changed through repository settings or configuration.

## Available Options

Since you cannot make logs private in a public repository, you have these alternatives:

### Option 1: Protect Sensitive Data (Recommended for Public Repos)

Keep your repository public but prevent sensitive data from appearing in logs:

1. **Use GitHub Secrets** - Store all sensitive data as repository secrets
2. **Automatic Masking** - GitHub automatically masks secret values in logs
3. **Manual Masking** - Use `::add-mask::` for additional protection
4. **Audit Workflows** - Regularly review workflows for potential data leaks
5. **Avoid Debug Output** - Never echo or print environment variables containing secrets

### Option 2: Move to Private Repository

If you absolutely need private workflow logs:
- Convert your repository to private
- All logs will then only be accessible to repository collaborators
- This is the only way to truly restrict log access

### Option 3: Disable Workflows

If workflows are exposing sensitive data and you can't fix them immediately:
- Disable specific workflows via GitHub UI or API
- This prevents new logs from being generated
- Note: This doesn't hide existing logs

## Best Practices for Securing Workflows in Public Repositories

### 1. Store All Sensitive Data in Secrets

```yaml
# ✅ GOOD - Using secrets
env:
  API_KEY: ${{ secrets.MY_API_KEY }}
  DATABASE_PASSWORD: ${{ secrets.DB_PASSWORD }}

# ❌ BAD - Hardcoded values
env:
  API_KEY: "sk-1234567890abcdef"
  DATABASE_PASSWORD: "MyP@ssw0rd"
```

### 2. Use Manual Masking for Dynamic Values

If you generate sensitive values during workflow execution:

```yaml
- name: Generate token and mask it
  run: |
    TOKEN=$(generate_token_command)
    echo "::add-mask::$TOKEN"
    echo "TOKEN=$TOKEN" >> $GITHUB_ENV
```

### 3. Never Echo Secrets

```yaml
# ❌ BAD - Don't do this
- name: Debug environment
  run: |
    echo "API Key: ${{ secrets.API_KEY }}"
    env | grep SECRET

# ✅ GOOD - Safe logging
- name: Verify configuration
  run: |
    echo "API Key is set: ${{ secrets.API_KEY != '' }}"
    echo "Configuration validated"
```

### 4. Sanitize URLs and Connection Strings

Be especially careful with URLs that might contain credentials:

```yaml
# ❌ BAD - Credentials in URL
- name: Clone repository
  run: git clone https://user:${{ secrets.TOKEN }}@github.com/org/repo.git

# ✅ GOOD - Use git credential helper or mask the URL
- name: Clone repository
  run: |
    URL="https://user:${{ secrets.TOKEN }}@github.com/org/repo.git"
    echo "::add-mask::$URL"
    git clone $URL
```

### 5. Review Third-Party Actions

Be cautious with third-party GitHub Actions:
- They may log inputs or environment variables
- Review their source code before use
- Prefer well-known, verified actions
- Consider pinning to specific versions (commit SHA)

### 6. Limit Workflow Permissions

Use the principle of least privilege:

```yaml
# Limit permissions to only what's needed
permissions:
  contents: read
  pull-requests: write
  # Don't grant unnecessary permissions
```

### 7. Use Environment Protection Rules

For production deployments:
- Use GitHub Environments with required reviewers
- Add deployment protection rules
- Limit who can approve deployments

## Audit Checklist for Existing Workflows

Use this checklist to audit your workflows:

- [ ] All API keys, passwords, and tokens stored in GitHub Secrets
- [ ] No secrets echoed or printed to logs
- [ ] No `env | grep` or similar commands that might expose secrets
- [ ] URLs with credentials are masked
- [ ] Database connection strings use secrets
- [ ] Azure/AWS credentials use secrets and are never logged
- [ ] Terraform plans don't expose sensitive variables
- [ ] Docker build args don't contain secrets
- [ ] Third-party actions are from trusted sources
- [ ] Workflow permissions follow least privilege principle
- [ ] Environment protection rules configured for production deployments

## Current Repository Status

This repository's workflows have been reviewed with the following findings:

### ✅ Good Security Practices Already in Place

1. **Secrets Management**: All sensitive credentials stored in GitHub Secrets:
   - `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET`, `ARM_SUBSCRIPTION_ID`, `ARM_TENANT_ID`
   - `TF_VAR_DB_ADMIN_PASSWORD`, `TF_VAR_OPENROUTER_API_KEY`, `TF_VAR_CLAUDE_API_KEY`
   - API keys properly referenced via `${{ secrets.SECRET_NAME }}`

2. **Masked Logging**: Secrets are not echoed or printed in workflows

3. **Environment Protection**: Production deployments require approval via `environment: production`

4. **Limited Permissions**: Workflows use specific permissions rather than defaults

### ⚠️ Potential Improvements

1. **Database URLs**: Connection strings containing passwords are marked with `# pragma: allowlist secret`
   - These are test credentials, acceptable for CI
   - Production credentials come from secrets

2. **Azure Outputs**: Some Azure CLI commands output FQDNs and resource information
   - These are public endpoints anyway, so not sensitive
   - No credentials are exposed

3. **Terraform Outputs**: Plan outputs might show resource configurations
   - Sensitive variables use secrets and won't be displayed
   - Infrastructure details are generally non-sensitive

## Recommended Actions for This Repository

Since this is a public repository with well-managed secrets, the current approach is appropriate:

1. ✅ **Keep using GitHub Secrets** for all sensitive data
2. ✅ **Continue using automatic masking** (already in place)
3. ✅ **Maintain environment protection rules** for production
4. ✅ **Regularly audit workflows** when adding new features

### When to Consider Private Repository

Consider converting to a private repository only if:
- You need to hide deployment infrastructure details
- Workflow logs reveal proprietary business logic
- Compliance requirements mandate private CI/CD logs
- You're exposing internal URLs or system architecture

For most open-source projects (including this one), keeping the repository public with proper secrets management is the correct approach.

## Additional Resources

- [GitHub Actions Security Best Practices](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
- [Using Secrets in GitHub Actions](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [Automatic Token Authentication](https://docs.github.com/en/actions/security-guides/automatic-token-authentication)
- [Security Hardening for Self-Hosted Runners](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions#hardening-for-self-hosted-runners)

## Summary

**You cannot make GitHub Actions logs private in a public repository.** This is by design and cannot be changed. Instead, focus on:

1. Storing all sensitive data in GitHub Secrets
2. Never echoing or printing secrets in workflows
3. Using manual masking for dynamically generated sensitive values
4. Regularly auditing workflows for potential data leaks
5. Considering a private repository only if truly necessary

The workflows in this repository already follow best practices and are appropriate for a public open-source project.
