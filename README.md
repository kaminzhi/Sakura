# Sakura

## Features

- **LinkFix:** You can use the `linkfix` command to convert link with [FxEmbed]("https://github.com/FxEmbed/FxEmbed").
- **AutoLinkFix:** You can enable this features to automatically convert links to [FxEmbed]("https://github.com/FxEmbed/FxEmbed") links.

## Getting Started

1. **Prerequisites:**

   - Ensure you have Python 3.11 or higher installed. (Recommended: 3.11)
   - Ensure you have Redis installed and running. (Recommended use Docker)
   - It is recommended to use [Poetry](https://python-poetry.org/) or `pip` for dependency management.

2. **Clone the Repository:**

   ```bash
   git clone https://https://github.com/kaminzhi/Sakura.git
   cd Sakura
   ```

3. **Install Dependencies:**

   - Using Poetry:

     ```bash
     poetry install
     ```

   - Using pip:

     ```bash
     pip install -r requirements.txt
     ```

4. **Configure Environment Variables:**

   - Copy the `example.env` file and rename it to `.env`.
   - Fill in your Discord Bot Token, Redis connection details, and Bot Owner IDs.
   - Example `.env` file:

     ```env
     DISCORD_TOKEN=your_discord_token
     REDIS_HOST=localhost
     REDIS_PORT=6379
     REDIS_PASSWORD=your_redis_password
     BOT_OWNER_IDS=1234567890,0987654321
     ```

5. **Run the Bot:**

   ```bash
   python bot/main.py
   ```

## Deployment (Docker Compose)

1. Ensure you have Docker and Docker Compose installed.
2. Run the following command in the project root:

   ```bash
   docker-compose up -d --build
   ```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
