# Sakura

## Features

- **LinkFix:** You can use the `linkfix` command to convert link with [FxEmbed]("https://github.com/FxEmbed/FxEmbed").
- **AutoLinkFix:** You can enable this features to automatically convert links to [FxEmbed]("https://github.com/FxEmbed/FxEmbed") links.

## Getting Started

1. **Prerequisites:**

   - Ensure you have Python 3.11 or higher installed. (Recommended: 3.11)
   - Ensure you have MongoDB installed and running. (Recommended use Docker)
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
