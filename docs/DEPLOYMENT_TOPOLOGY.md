# Deployment Topology

```text
Mobile --HTTPS--> reviewed ingress --> QR Server (Machine A) --> PostgreSQL
                                             |
                                             +--> NAS (LAN-only files/archive)
Desktop --------API/polling-----------------+
```

No direct client-to-NAS or Internet-to-PostgreSQL connection is permitted.
