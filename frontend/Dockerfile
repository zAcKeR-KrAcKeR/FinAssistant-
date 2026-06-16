FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
ARG VITE_API_URL=https://finassistant-production.up.railway.app
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build
EXPOSE 4173
CMD ["sh", "-c", "npx vite preview --host 0.0.0.0 --port ${PORT:-4173}"]
