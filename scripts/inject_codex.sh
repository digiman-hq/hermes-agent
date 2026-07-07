#!/bin/sh
# Inject the Linux aarch64 codex CLI binary into the running container.
# Ephemeral (lives in /usr/local/bin, lost on container recreate). For a
# durable install bake `RUN npm install -g @openai/codex` into the Dockerfile.
set -e
cd /tmp
echo "downloading codex 0.142.5 (aarch64-linux-musl)..."
curl -fsSL -o codex.tgz "https://github.com/openai/codex/releases/download/rust-v0.142.5/codex-aarch64-unknown-linux-musl.tar.gz"
tar xzf codex.tgz
bin="$(find /tmp -maxdepth 2 -name 'codex-aarch64-unknown-linux-musl' -type f | head -1)"
cp "$bin" /usr/local/bin/codex
chmod +x /usr/local/bin/codex
rm -f codex.tgz
echo -n "installed: "; /usr/local/bin/codex --version
