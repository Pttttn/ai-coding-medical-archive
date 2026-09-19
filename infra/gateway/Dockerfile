FROM nginx:1.28-alpine
RUN apk add --no-cache iptables
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY 15-egress.sh /docker-entrypoint.d/15-egress.sh
RUN chmod +x /docker-entrypoint.d/15-egress.sh
