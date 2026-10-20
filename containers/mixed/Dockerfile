# Compose the locally built, locked toolchain images; admission records immutable output IDs.
FROM darkfactory-native-adapters:0.3.0 AS node
FROM darkfactory-rust-tools:0.3.0
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
COPY --from=node /opt/factory-tools/node_modules/typescript /opt/factory-typescript
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && ln -s /opt/factory-typescript/bin/tsc /usr/local/bin/tsc
WORKDIR /workspace
