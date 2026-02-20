# GitHub Actions Security Quick Reference

> **TL;DR**: You cannot make workflow logs private in a public repository.
> Use GitHub Secrets and follow security best practices instead.

## Core Principle

**GitHub Actions logs in public repositories are ALWAYS PUBLIC** - this cannot be changed.

## What You Should Do

### ✅ DO

- Store ALL sensitive data in GitHub Secrets (Settings → Secrets and variables → Actions)
- GitHub will automatically mask secrets in logs
- Use `echo "::add-mask::$VALUE"` to mask dynamically generated secrets
- Regularly audit workflows for accidental secret exposure
- Use environment protection rules for production deployments
- Follow the principle of least privilege for workflow permissions

### ❌ DON'T

- Never hardcode secrets in workflow files
- Never echo/print secret values: `echo ${{ secrets.MY_SECRET }}`
- Never use `env | grep` or similar commands that might expose secrets
- Never include credentials in URLs without masking
- Don't trust unverified third-party actions with secrets

## Quick Examples

### Storing Secrets Correctly

```yaml
env:
  # ✅ GOOD
  API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
  DATABASE_URL: ${{ secrets.DATABASE_URL }}

  # ❌ BAD
  API_KEY: "sk-1234567890"  # pragma: allowlist secret
```

### Masking Dynamic Values

```yaml
- name: Generate and mask token
  run: |
    TOKEN=$(generate_token)
    echo "::add-mask::$TOKEN"
    echo "TOKEN=$TOKEN" >> $GITHUB_ENV
```

### Safe URL Handling

```yaml
# ❌ BAD - Credentials visible in logs
- run: git clone https://user:${{ secrets.TOKEN }}@github.com/org/repo.git

# ✅ GOOD - Mask the URL
- run: |
    URL="https://user:${{ secrets.TOKEN }}@github.com/org/repo.git"
    echo "::add-mask::$URL"
    git clone "$URL"
```

## Current Repository Status

✅ This repository follows best practices:

- All credentials stored in GitHub Secrets
- Secrets properly referenced via `${{ secrets.NAME }}`
- No secrets echoed or printed in workflows
- Production deployments use environment protection rules

## Need More Details?

See [docs/GITHUB_ACTIONS_SECURITY.md](../docs/GITHUB_ACTIONS_SECURITY.md) for comprehensive documentation including:

- Detailed explanation of GitHub's log visibility policy
- Complete audit checklist
- Advanced security patterns
- Troubleshooting guidance

## External Resources

- [GitHub: Security hardening for GitHub Actions](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
- [GitHub: Using secrets in GitHub Actions](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
