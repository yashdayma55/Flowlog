# Start from official Go image
FROM golang:1.23-alpine AS builder

WORKDIR /app

# Copy go mod files
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

RUN go mod tidy

# Build the binary
RUN go build -o log-processor main.go consumer.go processor.go

# Use minimal image for running
FROM alpine:latest

WORKDIR /app

# Copy binary from builder
COPY --from=builder /app/log-processor .

# Start command
CMD ["./log-processor"]