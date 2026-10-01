"""Single source of the site's public base URL.

Moved to the custom domain 10/01/2026 (reedos.github.io/stack_ledger/ now 301s to the
same path on reedos.dev). Every generator script and template placeholder must read the
URL from here, not repeat the literal, so a future host change is a one-line edit.
"""

SITE_URL = 'https://reedos.dev/stack_ledger/'
