---
name: Issue template
about: Template to create a general issue
title: ''
labels: ''
assignees: ''

---

Please provide as much information as possible, including screenshots, logging snippets and links to your repository, if it is public. Especially, link to the affected workflow that shows the issue that you are reporting.

For private repositories, please paste logs or your workflow yaml if you think this is relevant.

If the error occurs repeatedly, please consider adding this to the publish action, to collect more information on the issue:

```yaml
with:
  root_log_level: DEBUG
  log_level: DEBUG
```
