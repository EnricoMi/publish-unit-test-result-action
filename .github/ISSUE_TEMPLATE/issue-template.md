---
name: Issue template
about: Template to create a general issue
title: ''
labels: ''
assignees: ''

---

Please report if your repository is private. If it is public, please provide a link to the repository and the affected workflow.

If the error occurs repeatedly, please consider adding this to the publish action, to collect more information on the issue:

```yaml
with:
  root_log_level: DEBUG
  log_level: DEBUG
```
