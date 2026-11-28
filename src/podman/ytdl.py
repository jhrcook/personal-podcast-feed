"""Youtube downloads."""

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, FilePath


class YoutubeDownloadError(BaseException):
    """Error encountered when downloading from Youtube."""


class YoutubeDownloadInfo(BaseModel):
    """Parsed information from a Youtube download."""

    title: str
    description: str


class YoutubeDownload(BaseModel):
    """Youtube download result."""

    audio_file: FilePath
    info: YoutubeDownloadInfo


@dataclass
class YoutubeDownloadFiles:
    """Output files from a Youtube download."""

    audio_file: FilePath
    info_file: FilePath


def download_youtube_files(yt_url: str, output_dir: Path) -> YoutubeDownloadFiles:
    """Download the audio from a Youtube video."""
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError("Output direct must be a directory.")

    episode_dir = output_dir / "youtube-download"
    episode_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "64K",
        "-o",
        f"{episode_dir / 'episode.%(ext)s'}",
        "--write-info-json",
        yt_url,
    ]
    logger.info("Downloading Youtube audio...")
    tic = time.perf_counter()
    res = subprocess.run(cmd, check=False, capture_output=True)
    toc = time.perf_counter()
    logger.debug(f"Download process finished with exit code: {res.returncode}.")
    logger.debug(f"Download took {toc - tic:.1f} sec.")

    if res.returncode != 0:
        logger.debug(f"stdout: {res.stdout}")
        raise YoutubeDownloadError(res.stderr)
    logger.debug("Youtube download finished successfully.")

    downloaded_files = list(episode_dir.iterdir())
    if len(downloaded_files) != 2:
        raise YoutubeDownloadError(
            f"Expected two output files, found {len(downloaded_files):,d}."
        )

    organized_files: dict[str, Path] = {}
    for dnld_file in downloaded_files:
        if dnld_file.name.endswith("info.json"):
            organized_files["info_file"] = dnld_file
        else:
            organized_files["audio_file"] = dnld_file

    return YoutubeDownloadFiles(**organized_files)


def youtube_download(url: str, output_dir: Path) -> YoutubeDownload:
    ytdl_files = download_youtube_files(url, output_dir)
    logger.debug("Parsing Youtube download info JSON.")
    with ytdl_files.info_file.open("r") as f:
        ytdl_info = YoutubeDownloadInfo(**json.load(f))
    logger.debug(f"title: '{ytdl_info.title}'.")
    return YoutubeDownload(audio_file=ytdl_files.audio_file, info=ytdl_info)
