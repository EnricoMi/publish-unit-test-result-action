---
description: |
  This workflow is run after a dependabot pull request is created or rebased, to investigate the changes and enrich the pull request.

on:
  pull_request:
    types:
      - opened
      - synchronize
      - reopened
    branches:
      - dependabot/github_actions/*
  workflow_dispatch:
    inputs:
      pr-number:
        description: 'pull request #'
        required: true
        type: number

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

Enhance a dependabot pull-request that upgrades Github Actions in this repository.
This workflow is either triggered by the `pull_request` event, or via `workflow_dispatch`.
The former provides an associated pull request, the latter provides the number of the pull request as an input.

## Check event that triggered this workflow

- The `pull_request` event is only executed when triggered by dependabot on a Github Actions dependency upgrade.
- The `workflow_dispatch` is always executed.
- Only run for Github Action upgrade pull requests.
- Be very restrictive when hardening the condition that allows running this workflow, especially consider
  fork repositories and attacks with malicious pull request content.

## What to enhance

Enhance the respective pull request by:

- Suggest updating references of the same upgraded GitHub Action in README.md workflow examples (as PR suggestions/comments, not direct commits) so users see up-to-date usage.
- Summarizing code changes between the previous and new action versions by inspecting code diffs (not changelog text). Assess code changes regarding chances of introducing security risks, malicious code or exploitable bugs.
- Include functional changes summary.
- Summarizing changes of the Github Action's dependencies and respective security implications.

## Process

1. Identify the respctive pull request, use the pr-number input when run via workflow_run to determine the pull request to check
2. Check it is a dependabot Github Actions version upgrade, create by the respective bot
3. Update README.md if needed
4. Inspect code changes and summarize findings (create new pull request comment)
5. Inspect dependency changes and summarize findings (create separate pull request comment)
