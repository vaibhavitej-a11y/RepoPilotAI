from dotenv import load_dotenv

load_dotenv()
"""Main entry point for RepoPilot AI CLI."""
import asyncio
import os
import sys

from dotenv import load_dotenv
import click
from pydantic import ValidationError

load_dotenv()

from app.models.request import RepoAnalysisRequest


@click.group()
def cli():
    """RepoPilot AI — AI-Powered Software Engineering Intelligence Assistant."""
    pass


@cli.command()
@click.argument("target")
@click.option(
    "--source",
    type=click.Choice(["github", "filesystem"]),
    default="filesystem",
    help="Data source to analyze (github or filesystem)."
)
@click.option(
    "--branch",
    default="main",
    help="Branch to analyze (only applicable for github source)."
)
@click.option(
    "--max-files",
    default=200,
    type=int,
    help="Maximum files to scan (1 to 1000)."
)
@click.option(
    "--output",
    default="repopilot_report.md",
    help="Output file path for the final Markdown engineering report."
)
def analyze(target: str, source: str, branch: str, max_files: int, output: str):
    """Analyze a repository (local directory path or GitHub repo 'owner/repo')."""
    if not os.getenv("GEMINI_API_KEY"):
        click.secho(
            "GEMINI_API_KEY is not set. Add it to your environment or a .env file "
            "in the project root.",
            fg="red",
            err=True,
        )
        sys.exit(1)

    # Import after dotenv + API key check so ADK/Gemini are not initialized first.
    from app.agents.pipeline import run_pipeline

    click.echo(f"🚀 Starting RepoPilot analysis of: {target}")
    click.echo(f"⚙️  Configuration: Source={source} | Branch={branch} | MaxFiles={max_files}")

    # 1. Parse and validate the request via Pydantic
    try:
        request = RepoAnalysisRequest(
            data_source=source,  # type: ignore (validated by pydantic)
            repo_target=target,
            branch=branch,
            max_files_to_scan=max_files
        )
    except ValidationError as ve:
        click.secho(f"❌ Input validation failed: {ve}", fg="red", err=True)
        sys.exit(1)

    # 2. Run the asynchronous pipeline
    try:
        report = asyncio.run(run_pipeline(request))
    except Exception as e:
        click.secho(f"❌ Pipeline execution failed: {e}", fg="red", err=True)
        sys.exit(1)

    # 3. Output results
    click.echo("\n" + "=" * 50)
    click.secho("✅ Analysis Completed Successfully!", fg="green", bold=True)
    click.echo(f"🏆 Overall Engineering Score: {report.overall_score:.2f} / 10.0")
    click.echo(f"🕒 Analyzed At: {report.analyzed_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    click.echo("=" * 50 + "\n")

    click.echo("📄 Executive Summary:")
    click.echo(report.executive_summary)
    click.echo("\n" + "=" * 50)

    # 4. Save the markdown report to disk
    try:
        with open(output, "w", encoding="utf-8") as f:
            f.write(report.markdown_report)
        click.secho(f"💾 Complete Markdown report saved to: {output}", fg="cyan")
    except Exception as e:
        click.secho(f"⚠️ Failed to write report to {output}: {e}", fg="yellow", err=True)


if __name__ == "__main__":
    cli()
