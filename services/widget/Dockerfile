FROM node:20-alpine AS build
WORKDIR /app
COPY widget/package.json ./
RUN npm install
COPY widget/ .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/../public /usr/share/nginx/html
EXPOSE 80
