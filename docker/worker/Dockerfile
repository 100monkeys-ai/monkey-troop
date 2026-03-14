FROM rust:1.75 as builder

WORKDIR /app

# Copy workspace files
COPY Cargo.toml Cargo.lock ./
COPY shared ./shared
COPY worker ./worker

# Build release binary
RUN cargo build --release --bin monkey-troop-worker

# Runtime image
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    ca-certificates \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch for benchmarking
RUN pip3 install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

WORKDIR /app

# Copy binary and benchmark script
COPY --from=builder /app/target/release/monkey-troop-worker /usr/local/bin/
COPY coordinator/benchmark.py /app/

CMD ["monkey-troop-worker"]
