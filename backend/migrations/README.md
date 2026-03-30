# Alembic

初始化迁移：

```bash
uv run alembic revision --autogenerate -m "init schema"
uv run alembic upgrade head
```

当前模型来源：

- `src/nta_backend/models/auth.py`
- `src/nta_backend/models/dataset.py`
- `src/nta_backend/models/modeling.py`
- `src/nta_backend/models/jobs.py`
- `src/nta_backend/models/usage.py`
- `src/nta_backend/models/security.py`

