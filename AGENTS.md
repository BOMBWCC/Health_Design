# Always Apply Rules

1. **Prerequisite**: Read all docs in `memory-bank/` before writing any code.
2. **Architecture**: Maintain modularity. Follow the directory structure in `README.md`.
3. **Database**: Use Alembic for migrations. No manual SQL for schema changes.
4. **Security**: Mandatory `user_id` filtering on all data operations (Multi-tenancy).
5. **No Emoji**: Strictly forbidden in code, logs, comments, and commit messages.
6. **Testing**: TDD approach. Write tests before business logic.
7. **Time**: Full-chain UTC. Always use `datetime.now(timezone.utc)`.
8. **Documentation**: Update `memory-bank/architecture.md` and `memory-bank/progress.md` after each major feature.
9. **Decoupling**: Keep Pydantic schemas (API) strictly separated from SQLAlchemy models (DB).
