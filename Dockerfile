FROM node:25-alpine

WORKDIR /app

COPY llm/package*.json ./
RUN npm install

COPY llm/. .

EXPOSE 3000

CMD ["node", "server.js"]
