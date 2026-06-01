---
description: |
  This workflow is run after a dependabot pull request is created or rebased, to investigate the changes and enrich the pull request.

on:
  workflow_run:
    workflows: ["CI/CD"]
    types:
      - requested
    branches:
      - dependabot/github_actions/*

permissions:
  contents: read
  issues: read
  pull-requests: read

network: defaults

tools:
  github:
    # If in a public repo, setting `lockdown: false` allows
    # reading issues, pull requests and comments from 3rd-parties
    # If in a private repo this has no particular effect.
    lockdown: false
    min-integrity: none # This workflow is allowed to examine and comment on any issues

safe-outputs:
  mentions: false
  allowed-github-references: []
---

# Github Actions Dependabot pull-request enhancement workflow

Enhance a pull-request createdby dependabot that aims at upgrading Github Actions in this repository.
This workflow is triggered when the CI/CD workflow is started. Only enhance the corresponding pull-request

## Check event that triggered this workflow

- Only run for pull-request creation or rebase
- Only run when triggering workflow was triggered by dependabot
- Only run for Github Action upgrades
- Be very restrictive in hardening the condition that allows running this workflow, especially consider
  fork repositories and attacks with malicious pull request content


## What to enhance

Enhance the respective pull request by:

- Suggest updating references of the same upgraded GitHub Action in README.md workflow examples (as PR suggestions/comments, not direct commits) so users see up-to-date usage.
- Summarizing code changes between the previous and new action versions by inspecting code diffs (not changelog text). Assess code changes regarding chances of introducing security risks, malicious code or exploitable bugs.
- Include functional changes summary.
- Summarizing changes of the Github Action's dependencies and respective security implications.

## Process

1. Identify the respctive pull request
2. Check it is a Github Actions version upgrade
3. Update README.md if needed
4. Inspect code changes and summarize findings (create new pull request comment)
5. Inspect dependency changes and summarize findings (create separate pull request comment)
