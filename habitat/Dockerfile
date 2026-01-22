FROM node:22-alpine AS ui-builder
WORKDIR /app
COPY ui/package*.json ./ui/
RUN cd ui && npm ci
COPY . ./
RUN cd ui && npm run build

FROM golang:1.24-alpine AS go-builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . ./
COPY --from=ui-builder /app/internal/web/dist ./internal/web/dist
RUN CGO_ENABLED=0 go build -o habitat ./cmd/habitat

FROM alpine:3.19
RUN apk add --no-cache ca-certificates
COPY --from=go-builder /app/habitat /usr/local/bin/
EXPOSE 7890
ENTRYPOINT ["habitat", "run"]
