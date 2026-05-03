FROM node:20-alpine AS build

WORKDIR /app

COPY apps/web/package.json apps/web/package-lock.json /app/apps/web/
WORKDIR /app/apps/web
RUN npm ci

COPY apps/web /app/apps/web

ARG VITE_SYNAPSE_API_URL=http://localhost:8080
ARG VITE_SYNAPSE_WEB_BUILD=
ARG VITE_SYNAPSE_UI_FEATURES=
ENV VITE_SYNAPSE_API_URL=${VITE_SYNAPSE_API_URL}
ENV VITE_SYNAPSE_WEB_BUILD=${VITE_SYNAPSE_WEB_BUILD}
ENV VITE_SYNAPSE_UI_FEATURES=${VITE_SYNAPSE_UI_FEATURES}
RUN BUILD_LABEL="${VITE_SYNAPSE_WEB_BUILD:-$(date -u +%Y%m%d%H%M%S)}" \
    && FEATURE_LABEL="${VITE_SYNAPSE_UI_FEATURES:-synthesis_observability_panel,adoption_synthesis_graph,typed_synthesis_diagnostics}" \
    && export VITE_SYNAPSE_WEB_BUILD="${BUILD_LABEL}" \
    && export VITE_SYNAPSE_UI_FEATURES="${FEATURE_LABEL}" \
    && npm run build \
    && ENTRY_ASSET="$(basename "$(ls /app/apps/web/dist/assets/index-*.js | head -n 1)")" \
    && printf '{\"web_build\":\"%s\",\"generated_at\":\"%s\",\"ui_features\":\"%s\",\"entry_asset\":\"%s\"}\n' "${BUILD_LABEL}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${FEATURE_LABEL}" "${ENTRY_ASSET}" > /app/apps/web/dist/build.json

FROM nginx:1.27-alpine

COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/apps/web/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
