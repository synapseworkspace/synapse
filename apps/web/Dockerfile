FROM node:20-alpine AS build

WORKDIR /app

COPY apps/web/package.json apps/web/package-lock.json /app/apps/web/
WORKDIR /app/apps/web
RUN npm ci

COPY apps/web /app/apps/web

ARG VITE_SYNAPSE_API_URL=http://localhost:8080
ARG VITE_SYNAPSE_WEB_BUILD=
ARG VITE_SYNAPSE_UI_FEATURES=
ARG VITE_SYNAPSE_PUBLIC_BASE=./
ENV VITE_SYNAPSE_API_URL=${VITE_SYNAPSE_API_URL}
ENV VITE_SYNAPSE_WEB_BUILD=${VITE_SYNAPSE_WEB_BUILD}
ENV VITE_SYNAPSE_UI_FEATURES=${VITE_SYNAPSE_UI_FEATURES}
ENV VITE_SYNAPSE_PUBLIC_BASE=${VITE_SYNAPSE_PUBLIC_BASE}
RUN BUILD_LABEL="${VITE_SYNAPSE_WEB_BUILD:-$(date -u +%Y%m%d%H%M%S)}" \
    && FEATURE_LABEL="${VITE_SYNAPSE_UI_FEATURES:-synthesis_observability_panel,adoption_synthesis_graph,typed_synthesis_diagnostics}" \
    && PUBLIC_BASE_LABEL="${VITE_SYNAPSE_PUBLIC_BASE:-./}" \
    && export VITE_SYNAPSE_WEB_BUILD="${BUILD_LABEL}" \
    && export VITE_SYNAPSE_UI_FEATURES="${FEATURE_LABEL}" \
    && export VITE_SYNAPSE_PUBLIC_BASE="${PUBLIC_BASE_LABEL}" \
    && npm run build \
    && ENTRY_ASSET="$(basename "$(ls /app/apps/web/dist/assets/index-*.js | head -n 1)")" \
    && BUILD_LABEL_JSON="${BUILD_LABEL}" \
       GENERATED_AT_JSON="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
       FEATURE_LABEL_JSON="${FEATURE_LABEL}" \
       PUBLIC_BASE_JSON="${PUBLIC_BASE_LABEL}" \
       ENTRY_ASSET_JSON="${ENTRY_ASSET}" \
       node -e 'const fs=require("fs"); const payload={web_build:process.env.BUILD_LABEL_JSON, generated_at:process.env.GENERATED_AT_JSON, ui_features:process.env.FEATURE_LABEL_JSON, public_base:process.env.PUBLIC_BASE_JSON, entry_asset:process.env.ENTRY_ASSET_JSON}; fs.writeFileSync("/app/apps/web/dist/build.json", JSON.stringify(payload));'

FROM nginx:1.27-alpine

COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/apps/web/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
