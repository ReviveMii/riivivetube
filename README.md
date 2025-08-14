# RiiviveTube
A Revival for the Wii YouTube App

## Features
- Videos
- Pairing Devices
- Searching Videos
- Trending, Music, Gaming, Sports and News
- Search Suggestions in Search

## Bugs
- Random Crashes
- Videos randomly stop playing

## Setup
Download the WAD [here](https://revivemii.xyz/riivivetube) or from [WiiMart](https://wiimart.org) 


## (Optional) Self Hosting and Patching
Dump from your Wii / Download the Original YouTube WAD File

Download JPEXS Free Flash Decompiler [here](https://github.com/jindrapetrik/jpexs-decompiler/releases/tag/version24.0.1). Replace every new.old.errexe.xyz with your Server IP or Local IP (192.168.*.*:port) in the .swf files in RiiviveTube and save the SWF Files

Download [ShowMiiWads](https://wiibrew.org/wiki/ShowMiiWads) and [wszst](https://szs.wiimm.de/download.html) and unpack the WAD, unpack 00000002.app and open config/common.pcf and change dummy=1 to relax=2

Open trusted/wii_shim.sef and change https://www.youtube.com/ to http://yourserverip:port/ (with HTTP) and save the file

Repack 00000002.app and repack the WAD

Patch the WAD with Wiimmfi with the [RiiConnect WiiWare Patcher](https://github.com/RiiConnect24/WiiWare-Patcher/releases/tag/v2.2.2)

Open a private window in your Browser and login in YouTube, and go to robots.txt and export your Cookies in Netscape Format with a Browser Extension and close the Window, and save the Cookies in the RiiviveTube Folder in `c.txt`

Install the WAD on your Wii

Start the Server
