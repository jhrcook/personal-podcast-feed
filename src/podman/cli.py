"""Command line interface."""

from datetime import datetime
from pathlib import Path
from typing import Annotated

from typer import Argument, Option, Typer

from podman.manage_podcast import (
    build_all_feeds,
    cmd_add_episode,
    cmd_create_feed,
    cmd_cross_post,
)

app = Typer(help="Podcast feed production CLI")


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


def add_episode(
    audio_path: Annotated[
        Path, Argument(help="Path to a local audio file.", resolve_path=True)
    ],
    feed: Annotated[str, Option(help="Target feed key.")],
    title: Annotated[str | None, Option(help="Episode title.")] = None,
    description: Annotated[str | None, Option(help="Episode description.")] = None,
    published_at: Annotated[
        datetime | None,
        Option(help="Publication timestamp in ISO 8601 format with a timezone."),
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


def cross_post(
    to_feed: Annotated[str, Option("-t", "--to", help="Destination feed key")],
    episode_id: Annotated[
        str, Option("-e", "--episode", help="UUID or UUID fragment.")
    ],
) -> None:
    """Link an existing episode to another feed."""
    cmd_cross_post(to_feed=to_feed, episode_id=episode_id)


def rebuild() -> None:
    "Regenerate public feed files for GitHub Actions."
    build_all_feeds()


if __name__ == "__main__":
    app()
