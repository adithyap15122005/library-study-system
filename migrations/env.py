from alembic import context
from flask import current_app


def run_migrations():
    extension = current_app.extensions["migrate"]
    metadata = extension.db.metadata
    options = extension.configure_args
    if context.is_offline_mode():
        context.configure(
            url=extension.db.engine.url.render_as_string(hide_password=False),
            target_metadata=metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
            **options,
        )
        with context.begin_transaction():
            context.run_migrations()
    else:
        with extension.db.engine.connect() as connection:
            context.configure(connection=connection, target_metadata=metadata, **options)
            with context.begin_transaction():
                context.run_migrations()


run_migrations()
