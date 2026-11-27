import mimetypes
import os
import shutil
import uuid
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import format_datetime
from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from pydantic import BaseModel, DirectoryPath, Field, TypeAdapter

BASE_URL = os.environ.get("PODCAST_BASE_URL", "").rstrip("/")
PLACEHOLDER_PAGES_URL = "https://YOUR_USERNAME.github.io/YOUR_REPO"
FEEDS_FOLDER = Path("feeds")
PUBLIC_FOLDER = Path("public")
EPISODES_FOLDER = PUBLIC_FOLDER / "episodes"
COVERS_FOLDER = PUBLIC_FOLDER / "covers"
MASTER_CONFIG = Path("feed.yml")
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".opus"}
COVER_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MAX_GITHUB_FILE_SIZE_BYTES = 100 * 1024 * 1024

ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ET.register_namespace("itunes", ITUNES_NS)


class FeedConfiguration(BaseModel):
    """Feed configuration."""

    feed_id: str
    title: str | None
    description: str | None
    episodes: list[DirectoryPath] = Field(default_factory=list)
    cover: Path | None
    language: str = "en-us"

    def get_title(self) -> str:
        return self.title or self.feed_id


MasterConfiguration = dict[str, FeedConfiguration]
master_configuration_validator = TypeAdapter(MasterConfiguration)


def load_master_config() -> MasterConfiguration:
    if not MASTER_CONFIG.exists():
        return {}

    with MASTER_CONFIG.open("r") as f:
        return master_configuration_validator.validate_python(yaml.safe_load(f) or {})


def save_master_config(config: MasterConfiguration) -> None:
    config_python = {k: v.model_dump() for k, v in config.items()}
    with MASTER_CONFIG.open("w") as f:
        yaml.safe_dump(config_python, f, default_flow_style=False, sort_keys=False)


def sanitize_title(filename: str | Path) -> str:
    name = Path(filename).stem
    return name.replace("_", " ").replace("-", " ").strip().title()


def parse_published_at(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(value)
        except (AttributeError, ValueError) as exc:
            raise TypeError(
                "published timestamp must be a valid ISO 8601 value"
            ) from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TypeError(
            "published timestamp must include a timezone (for example, Z or +00:00)"
        )

    return parsed.astimezone(UTC)


def format_published_at(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def is_valid_feed_key(feed_key: str) -> bool:
    return bool(feed_key) and all(
        char.islower() or char.isdigit() or char == "-" for char in feed_key
    )


def find_audio_file(episode_dir: Path) -> Path | None:
    audio_files = sorted(
        path
        for path in episode_dir.iterdir()
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    )
    return audio_files[0] if audio_files else None


def audio_mime_type(audio_path: Path) -> str:
    guessed, _ = mimetypes.guess_type(audio_path.name)
    return guessed or "audio/mpeg"


def validate_publishable_file(file_path: Path) -> None:
    file_size = file_path.stat().st_size
    if file_size > MAX_GITHUB_FILE_SIZE_BYTES:
        raise ValueError(
            f"Error: '{file_path}' is {format_mib(file_size)}. GitHub blocks files "
            "larger than 100 MiB. Compress the file or use external object storage.",
        )


def format_mib(size_bytes: int) -> str:
    return f"{size_bytes / (1024 * 1024):.1f} MiB"


def public_url_path(path: Path) -> str:
    try:
        return path.relative_to(PUBLIC_FOLDER).as_posix()
    except ValueError:
        return path.as_posix()


def find_episode_by_id(episode_id: str) -> Path | None:
    if not EPISODES_FOLDER.exists():
        return None

    matches = sorted(
        path
        for path in EPISODES_FOLDER.iterdir()
        if path.is_dir() and episode_id in path.name
    )

    if len(matches) > 1:
        raise ValueError(
            f"Error: Episode ID '{episode_id}' matches multiple episode folders."
        )

    return matches[0] if matches else None


def create_base_feed(
    show_id: str, show_meta: FeedConfiguration
) -> tuple[ET.Element[str], ET.Element[str]]:
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    show_title = show_meta.title or show_id
    ET.SubElement(channel, "title").text = show_title
    ET.SubElement(channel, "description").text = (
        show_meta.description or "No description provided."
    )
    ET.SubElement(channel, "link").text = BASE_URL
    ET.SubElement(channel, "language").text = show_meta.language

    if show_meta.cover:
        cover_url = f"{BASE_URL}/{public_url_path(show_meta.cover)}"
        image = ET.SubElement(channel, f"{{{ITUNES_NS}}}image")
        image.set("href", cover_url)

        rss_image = ET.SubElement(channel, "image")
        ET.SubElement(rss_image, "url").text = cover_url
        ET.SubElement(rss_image, "title").text = show_title
        ET.SubElement(rss_image, "link").text = BASE_URL

    return rss, channel


def episode_metadata(
    episode_dir: Path, audio_path: Path
) -> tuple[str, str, str | None]:
    title = sanitize_title(audio_path.name)
    description = "No description provided."
    published_at = None
    metadata_path = episode_dir / "episode.yml"

    if metadata_path.exists():
        try:
            with metadata_path.open("r") as f:
                metadata = yaml.safe_load(f) or {}
            title = metadata.get("title") or title
            description = metadata.get("description") or description
            published_at = metadata.get("published_at")
        except yaml.YAMLError as exc:
            logger.warning(f"Could not parse {metadata_path}: {exc}.")

    return title, description, published_at


def resolve_publication_datetime(
    published_at: datetime | str | None, audio_path: Path, metadata_path: Path
) -> datetime:
    if published_at:
        try:
            return parse_published_at(published_at)
        except TypeError:
            logger.warning(
                f"Invalid published_at in {metadata_path}; using audio mtime."
            )

    return datetime.fromtimestamp(audio_path.stat().st_mtime, tz=UTC)


def build_all_feeds():
    if not BASE_URL:
        raise ValueError("PODCAST_BASE_URL is required when rebuilding feeds.")

    config = load_master_config()
    (PUBLIC_FOLDER / FEEDS_FOLDER).mkdir(parents=True, exist_ok=True)
    EPISODES_FOLDER.mkdir(parents=True, exist_ok=True)

    for show_key, show_meta in config.items():
        rss, channel = create_base_feed(show_key, show_meta)
        episodes = []
        for episode_path in show_meta.episodes:
            episode_dir = Path(episode_path)
            if not episode_dir.exists():
                logger.warning(f"Reference path {episode_dir} not found. Skipping.")
                continue

            audio_path = find_audio_file(episode_dir)
            if not audio_path:
                logger.warning(f"No audio file found in {episode_dir}. Skipping.")
                continue

            title, description, published_at = episode_metadata(episode_dir, audio_path)
            publication_datetime = resolve_publication_datetime(
                published_at, audio_path, episode_dir / "episode.yml"
            )
            episodes.append((publication_datetime, audio_path, title, description))

        for publication_datetime, audio_path, title, description in sorted(
            episodes, key=lambda episode: episode[0], reverse=True
        ):
            file_size = audio_path.stat().st_size
            pub_date = format_datetime(publication_datetime, usegmt=True)
            file_url = f"{BASE_URL}/{public_url_path(audio_path)}"

            item = ET.SubElement(channel, "item")
            ET.SubElement(item, "title").text = title
            ET.SubElement(item, "description").text = description
            ET.SubElement(item, "pubDate").text = pub_date

            enclosure = ET.SubElement(item, "enclosure")
            enclosure.set("url", file_url)
            enclosure.set("length", str(file_size))
            enclosure.set("type", audio_mime_type(audio_path))

            guid = ET.SubElement(item, "guid", isPermaLink="true")
            guid.text = file_url

        output_path = PUBLIC_FOLDER / FEEDS_FOLDER / f"{show_meta.feed_id}.xml"
        tree = ET.ElementTree(rss)
        ET.indent(tree, space="  ", level=0)
        with output_path.open("wb") as f:
            f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
            tree.write(f, encoding="utf-8", xml_declaration=False)

        logger.success(f"Rebuilt feed: {output_path}.")


def cmd_create_feed(
    show_key: str, title: str, description: str | None, cover: Path | None
) -> None:
    config = load_master_config()

    if not is_valid_feed_key(show_key):
        raise ValueError(
            "Feed key must use only lowercase letters, numbers, and hyphens."
        )

    if show_key in config:
        raise ValueError(f"Feed '{show_key}' already exists.")

    feed_id = str(uuid.uuid4())
    cover_path = None

    if cover:
        source_cover = cover.expanduser()
        if not source_cover.exists():
            raise ValueError(f"Cover file '{source_cover}' not found.")

        if source_cover.suffix.lower() not in COVER_EXTENSIONS:
            raise ValueError(f"'{source_cover}' is not a supported cover image.")

        validate_publishable_file(source_cover)
        COVERS_FOLDER.mkdir(parents=True, exist_ok=True)
        cover_path = COVERS_FOLDER / f"{feed_id}{source_cover.suffix.lower()}"
        shutil.copy2(source_cover, cover_path)

    config[show_key] = FeedConfiguration(
        feed_id=feed_id,
        title=title,
        description=description or f"The {title} podcast feed.",
        episodes=[],
        cover=cover_path,
    )

    save_master_config(config)
    logger.success(
        "Once you push these changes to GitHub, your new feed will be "
        f"available at:\n{PLACEHOLDER_PAGES_URL}/feeds/{feed_id}.xml"
    )


def cmd_add_episode(
    audio_path: Path,
    feed: str,
    title: str | None,
    description: str | None,
    published_at: datetime | None,
) -> None:
    config = load_master_config()

    if feed not in config:
        raise ValueError(f"Target feed '{feed}' does not exist.")

    if not audio_path.exists():
        raise ValueError(f"Local audio file '{audio_path}' not found.")

    if audio_path.suffix.lower() not in AUDIO_EXTENSIONS:
        raise ValueError(f"'{audio_path}' is not a supported audio file.")

    validate_publishable_file(audio_path)

    episode_dir = EPISODES_FOLDER / str(uuid.uuid4())
    episode_dir.mkdir(parents=True, exist_ok=True)

    destination = episode_dir / f"audio{audio_path.suffix.lower()}"
    shutil.copy2(audio_path, destination)

    published_at = published_at or datetime.now(UTC)
    episode = {"published_at": format_published_at(published_at)}
    if title or description:
        episode = {
            "title": title or sanitize_title(audio_path.name),
            "description": description or "No description provided.",
            **episode,
        }
    with (episode_dir / "episode.yml").open("w") as f:
        yaml.safe_dump(episode, f, default_flow_style=False, sort_keys=False)

    config[feed].episodes.append(episode_dir)
    save_master_config(config)
    logger.success(f"Episode added to '{feed}' at {episode_dir}")


def cmd_cross_post(to_feed: str, episode_id: str) -> None:
    config = load_master_config()

    if to_feed not in config:
        raise ValueError(f"Target feed '{to_feed}' does not exist.")

    episode_dir = find_episode_by_id(episode_id)

    if not episode_dir:
        raise FileNotFoundError(
            f"Error: Could not find an episode folder matching '{episode_id}'."
        )

    if episode_dir in config[to_feed].episodes:
        logger.info(f"Episode already cross-posted to '{to_feed}'.")
        return

    config[to_feed].episodes.append(episode_dir)
    save_master_config(config)
    logger.success(f"Cross-posted {episode_dir} to '{to_feed}'.")
