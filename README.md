# My personal podcast feed

This is my personal podcast feed for publishing audio from videos, non-podcast audio files, or text-to-speech converted audio files.
I used [zacharypodbela/githubio-podcast-hosting](https://github.com/zacharypodbela/githubio-podcast-hosting) as a template and have made my own changes to the code.

## Setup

### Create a virtual environment

```bash
uv venv
source .venv/bin/activate
uv sync
```

### Create a feed

```bash
podman create_feed \
    jhc-podcast \
    --title "JHC Podcast" \
    --description "My custom podcast feed." \
    --cover ./cover.jpeg
```

Feed URL: <https://{GH user name}.github.io/{GH repo name}/feeds/{feed UUID}.xml>

## Publishing episodes

### From an existing audio file

```bash
podman add-episode \
    episode.mp3 \
    --feed podcast-feed \
    --title "Episode title" \
    --description 'Episode description' # Optional
```

### Downloading from Youtube

```bash
brew install yt-dlp ffmpeg
podman add-youtube $YT_URL --feed podcast-feed
```

---

TODO:

- [X] data models in script
- [X] workflow to download from youtube, parse title and description, add episode
- [ ] add a simple home page to the GH Pages that just shows the available episodes (should get updated by GH Actions?)

Rinella on Huckberry

```bash
podman add-youtube "https://youtu.be/G4aaf5F5DIE" --feed jhc-podcast
```
