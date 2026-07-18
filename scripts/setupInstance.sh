#!/bin/bash


set -e
echo "(c) 2026 ReviveMii, TheErrorExe. All Rights Reserved"
echo ""
echo "========================================"
echo "  RiiviveTube Custom Instance Setup"
echo "========================================"
echo ""

read -p "Enter your custom server address (e.g. 192.168.1.100 or 192.168.1.100:5005, run 'ip a' to get your local IP. 5005 is the default port of RiiviveTube): " SERVER_ADDR

if [ -z "$SERVER_ADDR" ]; then
    echo "Error: No address provided. Exiting."
    exit 1
fi

echo ""
echo "Replacing ReviveMii Adress with '$SERVER_ADDR'..."

FILES=("main.py" "youtubei.py" "assets/leanback_ajax.json")

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        sed -i "s/ytv2.nossl.revivemii.xyz/$SERVER_ADDR/g" "$file"
        echo "  Patched: $file"
    else
        echo "  Warning: $file not found, skipping."
    fi
done

echo ""
echo "Downloading ReplaceInSwf..."

JAR_URL="https://github.com/ReviveMii/ReplaceInSwf/releases/download/v1.0.0/replace-in-swf-1.0.0.jar"
JAR_FILE="replace-in-swf-1.0.0.jar"

if [ ! -f "$JAR_FILE" ]; then
    if command -v wget &> /dev/null; then
        wget -q "$JAR_URL" -O "$JAR_FILE"
    elif command -v curl &> /dev/null; then
        curl -sL "$JAR_URL" -o "$JAR_FILE"
    else
        echo "Error: Neither wget nor curl is installed. Please install one of them."
        exit 1
    fi
    echo "  Downloaded: $JAR_FILE"
else
    echo "  $JAR_FILE already exists, skipping download."
fi

echo ""
echo "Patching .swf files"

if [ -d "assets" ]; then
    for swf in assets/*.swf; do
        if [ -f "$swf" ]; then
            filename=$(basename "$swf")
            echo "  Patching: $filename"
            java -jar "$JAR_FILE" "$swf" "$swf" "ytv2.nossl.revivemii.xyz" "$SERVER_ADDR" > /dev/null 2>&1
        fi
    done
else
    echo "  Warning: assets/ directory not found."
fi

echo ""
echo "========================================"
echo "  Done! Your instance is configured."
echo "  Server: $SERVER_ADDR"
echo "  Run 'main.py' to start it"
echo "========================================"
