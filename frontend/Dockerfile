FROM node:20-alpine AS build

WORKDIR /workspace

COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm install

COPY bid-buddy/package.json bid-buddy/package-lock.json ./bid-buddy/
RUN cd bid-buddy && npm install

COPY frontend ./frontend
COPY bid-buddy ./bid-buddy
COPY scripts ./scripts

RUN cd frontend && npm run build:all

FROM nginx:alpine

COPY --from=build /workspace/frontend/dist /usr/share/nginx/html

RUN printf 'server {\n\
  listen 80;\n\
  client_max_body_size 50M;\n\
  root /usr/share/nginx/html;\n\
  index index.html;\n\
  resolver 127.0.0.11 valid=10s ipv6=off;\n\
  set $api_upstream api:8000;\n\
  location /crm/ {\n\
    try_files $uri $uri/ /crm/index.html;\n\
  }\n\
  location / {\n\
    try_files $uri $uri/ /index.html;\n\
  }\n\
  location /api/ {\n\
    rewrite ^/api/?(.*)$ /$1 break;\n\
    proxy_pass http://$api_upstream;\n\
    proxy_set_header Host $host;\n\
    proxy_set_header X-Real-IP $remote_addr;\n\
  }\n\
}\n' > /etc/nginx/conf.d/default.conf

EXPOSE 80
