# Permissive intentions for the local demo (ACLs off). Production would scope
# these per service and enforce mTLS via Connect.
Kind = "service-intentions"
Name = "*"

Sources = [
  {
    Name   = "*"
    Action = "allow"
  },
]
