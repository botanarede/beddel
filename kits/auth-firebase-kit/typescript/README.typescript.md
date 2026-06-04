# auth-firebase-kit (TypeScript)

Status: **planned** — see story FB1.2.

The TypeScript implementation will live under `typescript/src/` and mirror the
Python API:

- `verifyIdToken(token)` — `firebase-admin/auth` `verifyIdToken`
- `verifyAppCheck(token)` — `firebase-admin/app-check` `verifyToken`
- `resolveTenant(uid, db, tenantId?)` — `@google-cloud/firestore`
- `firebaseAuthMiddleware()` — Next.js middleware (bonar-cms admin compatible)
