# Releasing

Releases pin the Docker image by digest, because Docker tags can be moved. A commit that
pins the action then also pins the image. The digest only exists after the image has been
published, so a release takes two commits on `master`. Here, `v2.26.0` is the new version.

## 1. Bump the version

Set the new version in these files and push to `master`:

| File                         | Value                                                                         |
|:-----------------------------|:------------------------------------------------------------------------------|
| `action.yml`                 | `image: 'docker://ghcr.io/enricomi/publish-unit-test-result-action:v2.26.0'` |
| `docker/action.yml`          | `docker_tag` default: `'v2.26.0'`                                             |
| `python/publish/__init__.py` | `__version__ = 'v2.26.0'`                                                     |

CI builds and publishes the image as `v2.26.0`, `v2.26` and `v2`. The summary of the
`Deploy to GitHub` job shows the values for the next step.

## 2. Pin the digest

Append the digest in these files and push to `master`:

| File                | Value                                                                                 |
|:--------------------|:--------------------------------------------------------------------------------------|
| `action.yml`        | `image: 'docker://ghcr.io/enricomi/publish-unit-test-result-action:v2.26.0@sha256:…'` |
| `docker/action.yml` | `docker_tag` default: `'v2.26.0@sha256:…'`                                            |

CI publishes no image from this commit. It checks that the digest matches the `v2.26.0` tag
in the registry, and the `Test Published Image` jobs run the pinned image on amd64 and arm64.

**Wait for CI to pass before continuing.** CI can't block the tag pushes below; it can only
report on them afterwards.

## 3. Tag the pinning commit

```bash
git tag v2.26.0 <commit from step 2>
git push origin v2.26.0
```

CI fails if this commit doesn't pin the image, or if the tag doesn't match the version in `action.yml`.

## 4. Move the major version tag

```bash
git tag --force v2 v2.26.0
git push --force origin v2
```

## If the pinned image fails

Don't overwrite the published `v2.26.0` image. Fix the problem and release `v2.26.1` instead.
The `v2` and `v2.26` image tags already moved in step 1, and move again with that release.
