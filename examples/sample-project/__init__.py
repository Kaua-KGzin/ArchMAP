"""
Sample project for ArchMAP — demonstrates dependency graph features.

Run:
    archmap analyze examples/sample-project --format both
    archmap serve   examples/sample-project

What you will see:
- A layered project with cli → app → core → utils dependencies
- One circular dependency between services and models
- A god module (api_gateway.py with many outgoing imports)
- Layer violation (utils importing from core)
"""
