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

Feed URL: <https://jhrcook.github.io/personal-podcast-feed/feeds/64f3f840-6e32-4def-acae-183cf5a435c4.xml>

### Publish and episode

```bash
podman add_episode \
    ./episode.mp3 \
    --feed jhc-podcast \
    --title "Episode title" \
    --description 'Episode description'
```

---

Downloading from Youtube

```bash
brew install yt-dlp ffmpeg

YT_URL="https://youtu.be/yVS1OTcvv94"
yt-dlp -x --audio-format mp3 --audio-quality 64K -o "episode.%(ext)s" --write-info-json "${YT_URL}"
```

TODO:

- [X] data models in script
- [ ] workflow to download from youtube, parse title and description, add episode
- [ ] add a simple home page to the GH Pages that just shows the available episodes (should get updated by GH Actions?)

Rinella on Huckberry

```bash
YT_URL="https://youtu.be/G4aaf5F5DIE"
yt-dlp -x --audio-format mp3 --audio-quality 64K -o "episode.%(ext)s" --write-info-json "${YT_URL}"

DESCRIPTION='Join Richard Greiner, Co-Founder of Huckberry, as he sits down with Steven Rinella - Outdoorsman, Author, and Founder of MeatEater - at the MeatEater studio in Bozeman, Montana. They dig into Steves incredible journey: from building one of the most influential outdoor media brands to raising kids and writing two bestselling childrens books, "Outdoor Kids in an Inside World" and "Catch a Crayfish, Count the Stars." Steven shares what sparked the creation of MeatEater, how he balances family life with running a business, and why getting kids outdoors is more important than ever. They explore the ethos of turning discomfort into resilience, the role of backyard adventures, and the future of ethical hunting and conservation.'

podman add-episode \
    ./episode.mp3 \
    --feed jhc-podcast \
    --title "Huckberry: Inside the Mind of Steven Rinella" \
    --description "${DESCRIPTION}"
```
