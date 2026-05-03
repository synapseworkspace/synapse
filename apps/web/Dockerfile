FROM node:20-alpine AS build

WORKDIR /app

COPY apps/web/package.json apps/web/package-lock.json /app/apps/web/
WORKDIR /app/apps/web
RUN npm ci

COPY apps/web /app/apps/web

ARG VITE_SYNAPSE_API_URL=http://localhost:8080
ARG VITE_SYNAPSE_WEB_BUILD=
ENV VITE_SYNAPSE_API_URL=${VITE_SYNAPSE_API_URL}
ENV VITE_SYNAPSE_WEB_BUILD=${VITE_SYNAPSE_WEB_BUILD}
RUN npm run build
RUN printf '{\"web_build\":\"%s\",\"generated_at\":\"%s\"}\n' "${VITE_SYNAPSE_WEB_BUILD:-unknown}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > /app/apps/web/dist/build.json

FROM nginx:1.27-alpine

COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/apps/web/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
