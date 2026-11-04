import typer

from sherlog import __version__

app = typer.Typer(help="Sherlog: investigate incidents with an LLM agent.", no_args_is_help=True)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"sherlog {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """Sherlog command line interface."""
