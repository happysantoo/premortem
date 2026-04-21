"""Premortem CLI. Run a what-if analysis on a topology YAML file.

Example:
    premortem examples/payment_contingency.yaml \\
        --target sanctions-check \\
        --mode "returns 500 for 80% of requests"
"""

from __future__ import annotations

from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from premortem.analyzer import analyze
from premortem.models import AnalysisReport, FailureInjection, Topology

app = typer.Typer(
    add_completion=False,
    help="Premortem: LLM-driven failure analysis for distributed system designs.",
)
console = Console()


def _load_topology(path: Path) -> Topology:
    with path.open() as f:
        data = yaml.safe_load(f)
    return Topology.model_validate(data)


def _impact_color(impact: str) -> str:
    return {
        "low": "green",
        "medium": "yellow",
        "high": "red",
        "critical": "bold red",
    }.get(impact, "white")


def _render(report: AnalysisReport, topology_name: str) -> None:
    console.rule(f"[bold cyan]premortem: {topology_name}")
    console.print(
        Panel(
            f"[bold]Target:[/bold] {report.failure.target}\n"
            f"[bold]Mode:[/bold] {report.failure.mode}",
            title="Failure injection",
            border_style="cyan",
        )
    )

    console.print("\n[bold underline]Summary[/bold underline]")
    console.print(Markdown(report.summary))

    console.print("\n[bold underline]Timeline[/bold underline]")
    timeline_table = Table(show_header=True, header_style="bold", show_lines=False)
    timeline_table.add_column("t+", justify="right", style="cyan", no_wrap=True)
    timeline_table.add_column("Component", style="magenta")
    timeline_table.add_column("What happens")
    for event in report.timeline:
        timeline_table.add_row(
            f"{event.t_seconds}s", event.component, event.description
        )
    console.print(timeline_table)

    console.print("\n[bold underline]Risks[/bold underline]")
    for i, risk in enumerate(report.risks, 1):
        color = _impact_color(risk.impact)
        console.print(
            Panel(
                f"[bold]{risk.title}[/bold]\n\n"
                f"Impact: [{color}]{risk.impact}[/{color}]   "
                f"Likelihood: {risk.likelihood}\n\n"
                f"{risk.explanation}",
                title=f"Risk {i}",
                border_style=color,
            )
        )

    console.print("\n[bold underline]Mitigations[/bold underline]")
    for i, m in enumerate(report.mitigations, 1):
        console.print(
            Panel(
                f"[bold]{m.title}[/bold]  [dim]pattern: {m.pattern}[/dim]\n"
                f"[dim]addresses:[/dim] {m.addresses_risk}\n\n"
                f"{m.description}\n\n"
                f"[yellow]Tradeoffs:[/yellow] {m.tradeoffs}",
                title=f"Mitigation {i}",
                border_style="green",
            )
        )


@app.command()
def run(
    topology_file: Path = typer.Argument(..., exists=True, help="Path to topology YAML."),
    target: str = typer.Option(..., "--target", "-t", help="Component id to fail."),
    mode: str = typer.Option(..., "--mode", "-m", help="Failure mode in plain English."),
    duration: int = typer.Option(60, "--duration", "-d", help="Duration in seconds."),
) -> None:
    """Run a premortem against a topology."""
    topology = _load_topology(topology_file)

    # Validate target exists
    try:
        topology.component(target)
    except KeyError as e:
        ids = ", ".join(c.id for c in topology.components)
        console.print(f"[red]Unknown component '{target}'.[/red] Known: {ids}")
        raise typer.Exit(code=1) from e

    failure = FailureInjection(target=target, mode=mode, duration_seconds=duration)

    with console.status(f"[cyan]Analyzing: {target} — {mode}..."):
        report = analyze(topology, failure)

    _render(report, topology.name)


@app.command()
def components(
    topology_file: Path = typer.Argument(..., exists=True, help="Path to topology YAML."),
) -> None:
    """List components in a topology (useful for picking --target)."""
    topology = _load_topology(topology_file)
    table = Table(title=topology.name, show_header=True, header_style="bold")
    table.add_column("id", style="cyan")
    table.add_column("kind", style="magenta")
    table.add_column("description")
    for c in topology.components:
        table.add_row(c.id, c.kind.value, c.description)
    console.print(table)


if __name__ == "__main__":
    app()
