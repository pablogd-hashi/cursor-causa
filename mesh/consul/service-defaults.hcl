# HTTP protocol on all mesh services so Connect applies L7 routing and Envoy
# emits per-request metrics (not just TCP connection counters).
Kind = "service-defaults"
Name = "web"
Protocol = "http"
---
Kind = "service-defaults"
Name = "api"
Protocol = "http"
---
Kind = "service-defaults"
Name = "payments"
Protocol = "http"
---
Kind = "service-defaults"
Name = "currency"
Protocol = "http"
---
Kind = "service-defaults"
Name = "cache"
Protocol = "http"
---
Kind = "service-defaults"
Name = "rates"
Protocol = "http"
