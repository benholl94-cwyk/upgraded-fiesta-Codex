FROM rust:1.85-slim-bookworm AS builder
WORKDIR /app
COPY . .
RUN cargo build --workspace --release

FROM debian:bookworm-slim
WORKDIR /app
COPY --from=builder /app/target/release/hm-gateway /app/hm-gateway
EXPOSE 8080
CMD ["/app/hm-gateway"]
