# Security Foundation

The database and NAS are not exposed directly to the Internet. Public mobile
traffic terminates at a reviewed HTTPS ingress and reaches the API on Machine A.
Identity is server-owned; local browser storage is not the sole long-lived
identity authority.

R002 accepts a transitional `X-Actor` API header for development/test actor
metadata only; it is not authentication. Client code has no NAS/storage path
access; storage keys are resolved and confined by the server-side storage
abstraction.
