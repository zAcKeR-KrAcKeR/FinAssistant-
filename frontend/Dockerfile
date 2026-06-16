FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
RUN npm install -g serve
COPY . .
ARG VITE_API_URL=https://finassistant-production.up.railway.app
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build
CMD ["sh", "-c", "serve -s dist -p ${PORT:-3000}"]
