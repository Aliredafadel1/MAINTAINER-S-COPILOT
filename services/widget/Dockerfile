FROM node:20-alpine AS build
WORKDIR /app
COPY widget/package.json ./
RUN npm install
COPY widget/ .
RUN npm run build

FROM nginx:alpine
COPY --from=build /public /usr/share/nginx/html
RUN printf 'server {\n  listen 80;\n  location / {\n    root /usr/share/nginx/html;\n    add_header Cache-Control "no-cache, no-store, must-revalidate";\n    add_header Pragma "no-cache";\n    add_header Expires "0";\n    add_header Access-Control-Allow-Origin "*";\n  }\n}\n' > /etc/nginx/conf.d/default.conf
EXPOSE 80
