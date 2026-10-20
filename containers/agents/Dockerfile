FROM node:22.22.3-bookworm-slim@sha256:e21fc383b50d5347dc7a9f1cae45b8f4e2f0d39f7ade28e4eef7d2934522b752
WORKDIR /opt/factory-tools
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts --no-audit --no-fund \
    && node node_modules/@anthropic-ai/claude-code/install.cjs \
    && ln -s /opt/factory-tools/node_modules/.bin/claude /usr/local/bin/claude \
    && ln -s /opt/factory-tools/node_modules/.bin/codex /usr/local/bin/codex \
    && ln -s /opt/factory-tools/node_modules/.bin/tsc /usr/local/bin/tsc
WORKDIR /workspace
