# Security Foundation

The database and NAS are not exposed directly to the Internet. Public mobile
traffic terminates at a reviewed HTTPS ingress and reaches the API on Machine A.
Identity is server-owned; local browser storage is not the sole long-lived
identity authority.

R002 accepts a transitional `X-Actor` API header for development/test actor
metadata only; it is not authentication. Client code has no NAS/storage path
access; storage keys are resolved and confined by the server-side storage
abstraction.

R009 file APIs accept a UUID/logical relation, never a client-supplied read
path. Upload names pass traversal, absolute/UNC/drive, reserved-name,
MIME/signature, and size checks before publication. Normal API responses omit
storage keys, physical roots, UNC paths, and credentials. Root configuration,
health, manual retry, and purge operations require the bounded storage-admin
boundary. Transfer logs store only classified, length-bounded summaries and
never file bytes or credentials.

R009A1 binds one immutable `AppConfig` to the files API at construction. The
request-time storage-admin guard never reloads ambient/default configuration.
The development-only `X-Storage-Admin` convenience header is accepted only
under explicitly injected DEV authority. STAGING and PROD require an injected
admin authorizer; when absent or unavailable, the request is denied before the
admin handler runs. A client environment/header cannot override the frozen app
environment.
