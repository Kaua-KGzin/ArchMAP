# Examples

## sample-project

A synthetic layered Python project that demonstrates every ArchMAP detection:

```
sample-project/
├── cli/main.py          ← entry layer (imports app)
├── app/service.py       ← application layer (imports core + utils)
├── app/controller.py    ← application layer (imports core + utils)
├── core/models.py       ← core layer (⚠ circular dep with validators)
├── core/validators.py   ← core layer (⚠ circular dep with models)
└── utils/logger.py      ← utils layer (⚠ layer violation: imports core)
```

What ArchMAP will detect:

- ✅ Full dependency graph across 4 layers
- 🔄 **Circular dependency** — `core/models.py ↔ core/validators.py`
- ⚠️ **Layer violation** — `utils/logger.py → core/models.py`

### Run it

```bash
# Analyze and export
archmap analyze examples/sample-project --format both

# Open interactive UI
archmap serve examples/sample-project
```
