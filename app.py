import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

import classifier
import config
import db
import embedder
import generator
import ingest
import retriever

console = Console()


def startup(conn) -> None:
    console.print(Panel("[bold cyan]Wikipedia RAG Assistant[/bold cyan]\nInitializing...", expand=False))
    db.init_db(conn)
    classifier.build_keyword_lists(conn)
    console.print("[green]✓[/green] Keyword lists loaded")
    embedder.load_embedding_model()
    console.print("[green]✓[/green] Embedding model loaded")
    embedder.get_chroma_client()
    console.print("[green]✓[/green] ChromaDB client ready")
    generator.load_llm()
    console.print("[green]✓[/green] LLM ready (Ollama)")
    console.print("\nType your question, or use a command:")
    console.print("  [bold]/ingest[/bold]   — ingest & embed all Wikipedia pages")
    console.print("  [bold]/sources[/bold]  — show sources from last answer")
    console.print("  [bold]/reset[/bold]    — clear screen")
    console.print("  [bold]/quit[/bold]     — exit\n")


def handle_ingest(conn) -> None:
    console.print("[yellow]Starting ingestion...[/yellow]")
    ingest.ingest_from_config_lists(conn)
    console.print("[yellow]Building embeddings...[/yellow]")
    embedder.run_embedding_pipeline(conn)
    classifier.build_keyword_lists(conn)
    console.print("[green]Done! All articles ingested and embedded.[/green]")


def show_sources(last_results: list[dict]) -> None:
    if not last_results:
        console.print("[yellow]No sources from the last query yet.[/yellow]")
        return
    table = Table(title="Sources Used", show_lines=True)
    table.add_column("Title", style="cyan", no_wrap=True)
    table.add_column("Category", style="magenta")
    table.add_column("Chunk", justify="right")
    table.add_column("Distance", justify="right")
    table.add_column("URL", style="blue")
    for r in last_results:
        table.add_row(
            r["title"],
            r["category"],
            str(r["chunk_index"]),
            f"{r['distance']:.4f}",
            r["url"],
        )
    console.print(table)


def handle_query(conn, query: str, last_results: list) -> None:
    with console.status("[bold green]Classifying query...[/bold green]"):
        category = classifier.classify_query(query)
    console.print(f"[dim]Query type: {category}[/dim]")

    with console.status("[bold green]Retrieving relevant chunks...[/bold green]"):
        results = retriever.retrieve(query, category)

    if not results:
        console.print(
            Panel(
                "I don't have enough information to answer that based on the available data.\n"
                "[dim]Tip: run [bold]/ingest[/bold] first if you haven't already.[/dim]",
                title="Answer",
                border_style="yellow",
            )
        )
        return

    last_results[:] = results
    docs = retriever.results_to_langchain_docs(results)

    try:
        with console.status("[bold green]Generating answer...[/bold green]"):
            response = generator.answer(query, docs)
    except ConnectionError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return

    console.print(Panel(Markdown(response), title="Answer", border_style="green"))


@click.command()
def run_cli():
    conn = db.get_connection()
    last_results: list[dict] = []

    try:
        startup(conn)
    except Exception as exc:
        console.print(f"[red]Startup error:[/red] {exc}")
        conn.close()
        sys.exit(1)

    while True:
        try:
            raw = console.input("[bold blue]You:[/bold blue] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        if not raw:
            continue

        cmd = raw.lower()

        if cmd in ("/quit", "/exit", "quit", "exit"):
            console.print("[dim]Goodbye.[/dim]")
            break
        elif cmd == "/reset":
            console.clear()
            last_results.clear()
        elif cmd.startswith("/sources"):
            show_sources(last_results)
        elif cmd.startswith("/ingest"):
            handle_ingest(conn)
        else:
            handle_query(conn, raw, last_results)

    conn.close()


if __name__ == "__main__":
    run_cli()
