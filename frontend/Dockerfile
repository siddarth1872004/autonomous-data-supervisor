FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json ./
RUN npm install --frozen-lockfile

COPY . .
RUN npm run build

# Production stage — nginx
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html

# Secure nginx config
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
