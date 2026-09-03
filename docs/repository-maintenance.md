# Repository Maintenance

This repository uses `main` as the stable integration branch. Test branches can exist locally, but they must not be pushed or merged unless they are intentionally promoted.

## Branch Rules

- `main` contains production-ready backend, frontend, infrastructure, documentation, and tests.
- `codex/kimi-frontend-docker` is a local test branch and must not be pushed or merged into `main`.
- Frontend experiments should use their own branch and only be promoted after review.
- Backend or infrastructure fixes should branch from the latest `main`.
- If a frontend branch needs backend updates, merge or rebase `main` into that branch. Do not merge the frontend test branch back into `main` by accident.

## What Should Stay Out Of Git

- `node_modules/` and package-manager caches.
- Temporary publish folders such as `.tmp-publish-*`.
- Local review/export folders such as `.docx-review/` and `output/`.
- Generated frontend build folders such as `dist/` and `dist-embed/`.
- Local `.env` files and deployment secrets.

## Safe Update Flow

```bash
git fetch origin --prune
git checkout main
git pull --ff-only origin main
```

Before pushing, check the branch and changed files:

```bash
git status --short --branch
git diff --name-only --cached
```

For the Kimi frontend test branch, avoid plain pushes. If the local guard is present, `git push` will fail because `pushRemote` points to `DISABLED_DO_NOT_PUSH_KIMI_FRONTEND`.

## Review Checklist

- Confirm the target branch is correct.
- Confirm no `node_modules`, `.env`, `.tmp-publish-*`, `.docx-review`, or `output` files are staged.
- Confirm generated frontend assets are intentional.
- Run focused tests or builds for the area changed.
- Keep branch-specific test work out of `main` until it is intentionally promoted.
