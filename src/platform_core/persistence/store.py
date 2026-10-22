import json
from contextlib import contextmanager
from typing import Any

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, create_engine, event, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from platform_core.models.tasks import utc_now


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(80), index=True)
    workflow: Mapped[str] = mapped_column(String(100))
    input_reference: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    started_at: Mapped[str] = mapped_column(String(40), default=utc_now)
    completed_at: Mapped[str | None] = mapped_column(String(40))
    error: Mapped[str | None] = mapped_column(String(200))
    result_json: Mapped[str | None] = mapped_column(Text)
    report_html: Mapped[str | None] = mapped_column(Text)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (UniqueConstraint("run_id", "stage"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    business_id: Mapped[str] = mapped_column(String(80))
    stage: Mapped[str] = mapped_column(String(100))
    component: Mapped[str] = mapped_column(String(100))
    input_reference: Mapped[str] = mapped_column(String(150))
    output_reference: Mapped[str | None] = mapped_column(String(150))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    started_at: Mapped[str | None] = mapped_column(String(40))
    completed_at: Mapped[str | None] = mapped_column(String(40))
    error: Mapped[str | None] = mapped_column(String(200))
    estimated_cost_usd: Mapped[str] = mapped_column(String(30), default="0.00")
    evaluation_json: Mapped[str | None] = mapped_column(Text)
    output_json: Mapped[str | None] = mapped_column(Text)


class Store:
    def __init__(self, database_url: str):
        kwargs: dict[str, Any] = {}
        if database_url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
        self.engine = create_engine(database_url, **kwargs)
        if self.engine.dialect.name == "sqlite":

            @event.listens_for(self.engine, "connect")
            def configure_sqlite(connection, _):
                connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def session(self):
        with self.sessions.begin() as session:
            yield session

    def run(self, run_id: str) -> dict | None:
        with self.session() as session:
            run = session.get(Run, run_id)
            if run is None:
                return None
            data = {c.name: getattr(run, c.name) for c in Run.__table__.columns}
            data["result"] = json.loads(data.pop("result_json")) if run.result_json else None
            data.pop("report_html")
            tasks = session.scalars(select(Task).where(Task.run_id == run_id).order_by(Task.started_at)).all()
            data["tasks"] = []
            for task in tasks:
                item = {
                    c.name: getattr(task, c.name) for c in Task.__table__.columns if c.name != "output_json"
                }
                item["evaluation"] = json.loads(item.pop("evaluation_json")) if task.evaluation_json else None
                data["tasks"].append(item)
            return data

    def report(self, run_id: str) -> str | None:
        with self.session() as session:
            run = session.get(Run, run_id)
            return run.report_html if run else None
