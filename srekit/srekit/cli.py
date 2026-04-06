import typer

from srekit.cmd_scan import scan
from srekit.cmd_audit import audit
from srekit.cmd_incident import incident_app
from srekit.cmd_report import report

app = typer.Typer(
    name="srekit",
    help="CLI toolkit for the Intelligent SRE Platform",
    no_args_is_help=True,
)

app.command()(scan)
app.command()(audit)
app.add_typer(incident_app, name="incident")
app.command()(report)

if __name__ == "__main__":
    app()
