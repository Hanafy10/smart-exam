FROM node:20-alpine AS builder

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend ./
RUN mkdir -p /app/public

ARG NEXT_PUBLIC_API_URL=http://192.168.1.9:8000
ARG NEXT_PUBLIC_WS_URL=ws://192.168.1.9:8000/ws/dashboard
ARG NEXT_PUBLIC_DEFAULT_LOGIN_USER=admin
ARG NEXT_PUBLIC_DEFAULT_LOGIN_PASS=Admin@12345678

ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL
ENV NEXT_PUBLIC_DEFAULT_LOGIN_USER=$NEXT_PUBLIC_DEFAULT_LOGIN_USER
ENV NEXT_PUBLIC_DEFAULT_LOGIN_PASS=$NEXT_PUBLIC_DEFAULT_LOGIN_PASS
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["npm", "run", "start"]
