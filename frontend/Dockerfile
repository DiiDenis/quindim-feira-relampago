# syntax=docker/dockerfile:1

FROM node:22.22.3-alpine AS dependencias

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

FROM dependencias AS construcao

COPY . .
RUN npm run build

FROM node:22.22.3-alpine AS runtime

ENV NODE_ENV=production \
    NITRO_HOST=0.0.0.0 \
    NITRO_PORT=3000

WORKDIR /app

COPY --from=construcao --chown=node:node /app/.output ./.output

USER node

EXPOSE 3000

CMD ["node", ".output/server/index.mjs"]
