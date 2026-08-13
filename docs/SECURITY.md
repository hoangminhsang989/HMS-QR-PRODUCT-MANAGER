# Security Foundation

The database and NAS are not exposed directly to the Internet. Public mobile
traffic terminates at a reviewed HTTPS ingress and reaches the API on Machine A.
Identity is server-owned; local browser storage is not the sole long-lived
identity authority.
