# QuestFantasy Backend
## Overview
In QuestFantasy backend 

# Prepare environment variables
Copy `.env.example` to `.env` and edit values:

- `SECRET_KEY`: Set a strong random string
- `DEBUG=False`: For safer defaults
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`: Set secure credentials for database
- `TOKEN_TTL_SECONDS`: Login session token expiration in seconds

## Prerequisites

Before starting the deployment, ensure your system meets the following requirements:

- Ubuntu operating system (or other Linux distribution)
- Administrator privileges (sudo)
- Internet connection (for downloading Docker and related packages)

If your system meets these requirements, you can simply skip the following tools installation.

## Installing Required Tools

### Step 1: Update System Packages

First, update the system package list and upgrade existing packages:

```bash
sudo apt update && sudo apt upgrade -y
```

### Step 2: Install Docker

Install necessary dependencies:

```bash
sudo apt install -y ca-certificates curl gnupg
```

Add Docker official GPG key:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

Setup Docker official repository:

```bash
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

Update package:

```bash
sudo apt update
```

Install Docker and its related components:

```bash
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### Step 3: Add User to Docker Group

To avoid needing `sudo` for every Docker command, add the current user to the Docker group:

```bash
sudo groupadd docker
sudo usermod -aG docker $USER
```

**Important:** After executing the above commands, you need to log out and log back in, or execute the following command to make the group change take effect immediately:

```bash
newgrp docker
```

### Step 4: Start Docker Service

Start the Docker service and enable it to start on boot:

```bash
sudo systemctl start docker
sudo systemctl enable docker
```

### Step 5: Verify Docker Installation

Verify that Docker is correctly installed:

```bash
docker --version
docker compose version
```

If both commands display version numbers, the installation is successful.

## Start services
```bash
docker compose up --build -d
```

## Check status
```bash
docker compose ps
docker compose logs -f web
```

## Stop services
```bash
docker compose down
```

## Reset database (danger)
This removes all PostgreSQL data:
```bash
docker compose down -v
```

## Notes
- User passwords are stored hashed by Django auth.
- Token authentication is configured with server-side expiration.
- The `web` container applies migrations on startup automatically.