# Use Node.js 20 LTS
FROM node:20-alpine

WORKDIR /app

# Install dependencies (full set needed for tsc)
COPY package*.json ./
RUN npm install

# Build TypeScript
COPY tsconfig.json ./
COPY src ./src
RUN npm run build

# Drop dev deps for runtime
RUN npm prune --production

ENV NODE_ENV=production
ENV HOST=0.0.0.0
# Do NOT hardcode PORT — let Zeabur inject it.

CMD ["node", "dist/index.js"]