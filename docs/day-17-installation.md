# Day 17 — Installation and smoke test

Day 17 extends the existing Day 16 installation. Preserve the current virtual environment, frontend dependencies, `.env.local`, Git metadata, and `~/.repox` workspace.

## Backend

From the repository root, activate the existing virtual environment and start:

```powershell
python -m uvicorn repox.api.app:app --reload
```

## Frontend

In a second terminal:

```powershell
cd frontend
pnpm dev
```

Open `http://localhost:3000`, select an indexed Python repository, and choose **Debug an issue**.

## Smoke test

1. Enter a short bug description.
2. Paste a Python traceback with at least one `File "...", line N, in ...` frame.
3. Select **Investigate**.
4. Confirm the exception and frames are parsed in execution order.
5. Confirm the report contains repository-grounded evidence and source citations, or a clear no-evidence response.
6. Confirm an empty submission is blocked by the UI and rejected by the API with HTTP 422.

The endpoint is `POST /repositories/{repository_id}/debug`. Example request:

```json
{
  "description": "The request fails when the input list is empty.",
  "traceback": "Traceback (most recent call last):\\n  File \\\"src/service.py\\\", line 31, in process\\nIndexError: list index out of range"
}
```
