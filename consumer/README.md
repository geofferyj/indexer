# Blockchain Indexer for EVM Chains

This project implements a blockchain indexer for EVM-compatible chains using Python, asyncio, and Redis. The indexer processes blocks, transactions, and receipts, and publishes the data to Redis Streams. It is designed to be efficient, scalable, and easy to integrate with other services using the provided SDK.

## **Features**

- **Asynchronous Processing**: Utilizes `asyncio` and `aiohttp` for non-blocking operations.
- **Redis Integration**: Uses Redis Streams and Pub/Sub for data streaming and inter-process communication.
- **SDK**: Provides a Python SDK for interacting with the indexer service.
- **Logging**: Comprehensive logging using `loguru` for easy debugging and monitoring.
- **Metrics**: Exposes Prometheus metrics for monitoring performance and health.
- **Error Handling**: Implements retries with exponential backoff and handles chain reorganizations.

---

## **Table of Contents**

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Setup and Installation](#setup-and-installation)
- [Running the Indexer Service](#running-the-indexer-service)
- [Using the SDK](#using-the-sdk)
  - [Connecting to the Service](#connecting-to-the-service)
  - [Adding a Chain](#adding-a-chain)
  - [Listing Chains](#listing-chains)
  - [Getting Status](#getting-status)
  - [Removing a Chain](#removing-a-chain)
- [Monitoring](#monitoring)
- [Configuration](#configuration)
- [Logging](#logging)

---

## **Architecture**

The indexer service runs as a separate process and listens for commands via Redis Pub/Sub channels. Clients interact with the service using the provided SDK, which sends commands and receives responses through Redis.

- **Service**: Processes blocks and transactions, handles chain management, and exposes metrics.
- **SDK**: Allows clients to add/remove chains, list chains, and get status information.

---

## **Prerequisites**

- **Docker** and **Docker Compose**
- **Python 3.10** or higher (for running the SDK or example scripts)
- **Redis** (managed by Docker Compose)

---

## **Setup and Installation**

1. **Clone the Repository**

   ```bash
   git clone https://github.com/yourusername/blockchain-indexer.git
   cd blockchain-indexer
   ```

2. **Install Dependencies**

    The service uses Poetry for dependency management.

    ```bash
    poetry install
    ```

## **Running the Indexer Service**

Use Docker Compose to build and start the indexer service along with Redis, Prometheus, and Grafana.

```bash 
docker compose up --build
```

This command will:

-   Build the Docker image for the indexer service.
-   Start the indexer service, Redis, Prometheus, and Grafana containers.

## **Using the SDK**
The SDK allows you to interact with the indexer service from your Python applications.

### **Connecting to the Service**

```bash 
import asyncio
from sdk import IndexerClient

async def main():
    client = IndexerClient()
    await client.connect()
    # Perform operations...
    await client.disconnect()

asyncio.run(main())
```

### **Adding a Chain**

```bash
from sdk.models import ChainConfig

config = ChainConfig(
    chain_id="ethereum",
    rpc_endpoint="https://mainnet.infura.io/v3/YOUR_INFURA_PROJECT_ID",
    block_time=15
)
response = await client.add_chain(config)
print("Add Chain Response:", response)

Listing Chains

chains = await client.list_chains()
print("Chains:", chains)
```

### **Getting Status**

```bash
status = await client.get_status()
print("Status:", status)
```

### **Removing a Chain**
```bash
response = await client.remove_chain("ethereum")
print("Remove Chain Response:", response)
```

## **Monitoring**

**Prometheus**

The indexer service exposes metrics on port 8001. Prometheus is configured to scrape these metrics.

Access Prometheus at:

```
http://localhost:9090
```

**Grafana**

Grafana is set up for visualizing metrics.

Access Grafana at:

```
http://localhost:3000
```

Default login credentials:
- Username: admin
- Password: admin

## **Configuration**

**Service Configuration**

Configuration settings can be adjusted in service/config.py or via environment variables.

Key settings include:
- REDIS_URL: Redis connection URL.
- METRICS_PORT: Port for exposing Prometheus metrics.
- LOG_LEVEL: Logging level (e.g., DEBUG, INFO, WARNING).

Logging

The service and SDK use loguru for logging. Logs include detailed information about events and errors.
- Service Logs: Output to the console by default.
- SDK Logs: Output to the console when using the SDK.

Adjust logging levels as needed for debugging or production environments.

---