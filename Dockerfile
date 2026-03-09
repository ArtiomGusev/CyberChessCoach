FROM node:20-alpine

ENV NODE_ENV=production

WORKDIR /app

COPY llm/package*.json ./
RUN if [ -f package-lock.json ]; then npm ci --omit=dev --no-audit --no-fund; else npm install --omit=dev --no-audit --no-fund; fi

COPY llm/. .
RUN chown -R node:node /app

USER node

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD node -e "const http=require('http'); const req=http.get('http://127.0.0.1:3000/health', res=>process.exit(res.statusCode===200?0:1)); req.on('error', ()=>process.exit(1)); req.setTimeout(4000, ()=>{req.destroy(); process.exit(1);});"

CMD ["node", "server.js"]
