FROM node:20-slim

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install

COPY . .

# Baked in at build time — see src/api.js. Passed through by
# docker-compose.yml's build.args.
ARG VITE_API_BASE=http://localhost:9001
ENV VITE_API_BASE=${VITE_API_BASE}
RUN npm run build

EXPOSE 8081
# `vite preview` is a small, dependency-light static server for the built
# dist/ — perfectly adequate for a reference example; a real production
# deployment would put a proper web server (nginx, etc.) in front instead.
CMD ["npm", "run", "preview"]
