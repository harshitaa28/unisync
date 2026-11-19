FROM node:18-slim
RUN apt-get update && apt-get install -y python3 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
EXPOSE 3000
CMD ["node", "server.js"]
