# Applying the Day 16 update

1. Stop the RepoX backend and frontend development servers.
2. Extract `RepoX_Day16.zip` into a temporary directory.
3. Copy the extracted project contents into the existing RepoX root and replace
   matching source files.
4. Preserve the existing `.git`, `.venv`, `frontend/node_modules`,
   `frontend/.env.local`, and the local `~/.repox` workspace.
5. Restart the backend from the RepoX root:

   ```powershell
   python -m uvicorn repox.api.app:app --reload
   ```

6. In a second terminal, start the frontend from `frontend/`:

   ```powershell
   pnpm dev
   ```

7. Open the Code Graph view for an indexed repository. It now requests live
   graph data from `GET /repositories/{repository_id}/graph`.

The default language registry enables Python only. Existing repository indexes
remain in place; the graph endpoint performs deterministic analysis from the
checkout and does not rebuild embeddings.
