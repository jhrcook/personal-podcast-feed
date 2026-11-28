"""Command line interface."""

import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from typer import Argument, Option, Typer

from podman.manage_podcast import (
    build_all_feeds,
    cmd_add_episode,
    cmd_create_feed,
    cmd_cross_post,
)
from podman.ytdl import youtube_download

app = Typer(help="Podcast feed production CLI", add_completion=False)


def git_commit_new_episode(title: str) -> None:
    if typer.confirm(f"Commit new episode '{title}'?"):
        subprocess.run(["git", "add", "feed.yml", "public/episodes"], check=True)
        subprocess.run(
            ["git", "commit", "--message", f"episode: '{title}'"], check=True
        )


@app.command()
def create_feed(
    feed: Annotated[str, Argument(help="Feed key used by other CLI commands.")],
    title: Annotated[
        str, Option("-t", "--title", help="Human-readable podcast title.")
    ],
    description: Annotated[
        str | None, Option("-d", "--description", help="Overall podcast summary")
    ] = None,
    cover: Annotated[
        Path | None, Option("-c", "--cover", help="Path to feed cover art")
    ] = None,
) -> None:
    """Create a new show feed."""
    cmd_create_feed(show_key=feed, title=title, description=description, cover=cover)


@app.command()
def add_episode(
    audio_path: Annotated[
        Path, Argument(help="Path to a local audio file.", resolve_path=True)
    ],
    feed: Annotated[str, Option("-f", "--feed", help="Target feed key.")],
    title: Annotated[str | None, Option("-t", "--title", help="Episode title.")] = None,
    description: Annotated[
        str | None, Option("-d", "--description", help="Episode description.")
    ] = None,
    published_at: Annotated[
        datetime | None,
        Option(
            "-p",
            "--published-at",
            help="Publication timestamp in ISO 8601 format with a timezone.",
        ),
    ] = None,
) -> None:
    """Import audio into a feed."""
    if published_at is not None and (
        published_at.tzinfo is None or published_at.utcoffset() is None
    ):
        raise ValueError(
            "Published timestamp must include a timezone (for example, Z or +00:00)."
        )

    cmd_add_episode(
        audio_path=audio_path,
        feed=feed,
        title=title,
        description=description,
        published_at=published_at,
    )
    # TODO: Refactor `cmd_add_episode` to have a result type with final title and
    # use that in `git_commit_new_episode`.
    git_commit_new_episode(title or audio_path.name)


@app.command()
def cross_post(
    to_feed: Annotated[str, Option("-t", "--to", help="Destination feed key")],
    episode_id: Annotated[
        str, Option("-e", "--episode", help="UUID or UUID fragment.")
    ],
) -> None:
    """Link an existing episode to another feed."""
    cmd_cross_post(to_feed=to_feed, episode_id=episode_id)


@app.command()
def rebuild() -> None:
    "Regenerate public feed files for GitHub Actions."
    build_all_feeds()


@app.command()
def add_youtube(
    url: Annotated[str, Argument(help="Youtube URL.")],
    feed: Annotated[str, Option("-f", "--feed", help="Target feed key.")],
    title: Annotated[
        str | None,
        Option(
            "-t",
            "--title",
            help="Optional replacement episode title; "
            "overrides the one of the Youtube video.",
        ),
    ] = None,
    description: Annotated[
        str | None,
        Option(
            "-d",
            "--description",
            help="Optional replacement episode description; "
            "overrides the one of the Youtube video.",
        ),
    ] = None,
) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        ytdl = youtube_download(url, Path(temp_dir))
        title = title or ytdl.info.title
        add_episode(
            audio_path=ytdl.audio_file,
            feed=feed,
            title=title or ytdl.info.title,
            description=description or ytdl.info.description,
        )
        git_commit_new_episode(title)
