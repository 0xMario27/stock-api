# 前端 Dockerfile：多阶段构建，node 构建 + nginx 托管 + API 反代

# 第一阶段：构建前端静态资源
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

# 第二阶段：nginx 托管 + 反代后端 API
FROM nginx:alpine AS runtime

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
