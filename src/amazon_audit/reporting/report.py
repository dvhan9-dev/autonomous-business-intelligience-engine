from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def render_report(result: dict) -> str:
    environment = Environment(
        loader=FileSystemLoader(Path(__file__).parent / "templates"), autoescape=select_autoescape(["html"])
    )
    return environment.get_template("audit.html").render(audit=result)
