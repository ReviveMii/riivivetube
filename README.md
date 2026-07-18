# RiiviveTube
A Revival for the Wii YouTube App

## Using the Public Instance
Download the prepatched WAD [here](https://revivemii.xyz/riivivetube) or [patch your own WAD](https://github.com/ReviveMii/ReviveMiiPatcher)

## Hosting your own Instance
**RiiviveTube currently only supports Linux.** While running this on Windows may work, it is not supported

**Requirements**: ffmpeg, git, python3 and pip

Setup the Instance: ```git clone https://github.com/ReviveMii/riivivetube && cd riivivetube && bash scripts/setupInstance.sh```
Install the dependencies: ```pip install -r requirements.txt``` 
Start the Server (standard port is 5005): ```python3 main.py```

Use the [Patcher](https://github.com/ReviveMii/ReviveMiiPatcher) to patch your WAD for your Instance

If you want to avoid YouTube blocking your IP, use a [cookies.txt file](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp)

## Working Features
- Search and play videos
- Music, Gaming, Sports and News
- Search Suggestions in Search
- Sign-in (partially working)

## TODO
- Higher video quality
- Fix 0 views on watch_later and watch_history (Signed-In)
- Implement subscriptions, etc (Signed-In)
- Implement Pairing/Lounge API Proxy

## Bugs
- Random crashes (some have been patched)

## Discord
Join our [Discord](https://discord.gg/yHva2ncjyx)

## Credits
- [Liinback](https://github.com/RedFireMRT84/Liinback-v3) (RiiviveTube uses some XML functions from Liinback)
- [yt2009-wii](https://github.com/erievs/yt2009-wii) (RiiviveTube's SWF Files are based of the yt2009wii SWF files)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) (RiiviveTube uses YT-DLP to extract video streams and subtitles)
- [ffmpeg](https://ffmpeg.org/) (used for converting videos)
