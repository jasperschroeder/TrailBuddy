# TrailBuddy

**A personal hiking journal + AI trail co-pilot**

This project started out as a pet project for me to practice modern AI engineering and product ownership, while hoping that this turns into something that is actually helpful and which I will continue using.

Idea is to create a lightweight application to log hikes, GPX routes and lap times, as well as notes about what was great (or terrible) about a hike for an AI model to remember the hiking history and be able to have a *personalized* chat history.
Personal hiking journal plus AI trail co-pilot that runs locally and keeps your hiking data private.

TrailBuddy lets you log hikes from GPX and CSV files, visualize routes, track performance over time, and chat with an AI assistant that answers from your own hiking history.

## Features

- Upload GPX routes and optional CSV split or lap data
- Track distance, elevation gain, duration, date, and notes
- Explore hike history with interactive OpenStreetMap views
- Ask TrailBuddy questions using hybrid SQL plus semantic retrieval
- Keep data local by default with no required cloud backend

## Tech Stack

- App UI: Streamlit
- Mapping: Folium plus OpenStreetMap
- Data: SQLite
- AI orchestration: LangChain
- Vector search: ChromaDB
- Embeddings: Sentence Transformers
- Local LLM: Ollama
- Parsing and analytics: GPX parsing plus Pandas

## Getting Started

### Using Docker (Recommended)

The easiest way to run TrailBuddy is using Docker Compose. This will set up both the application and the Ollama AI service automatically.

1.  **Clone the repository.**
2.  **Run Docker Compose:**
    ```bash
    docker compose up --build
    ```
3.  **Access the app:** Open [http://localhost:8501](http://localhost:8501) in your browser.

*Note: On the first run, the `model-puller` service will download the AI model specified in the `.env` file (defaults to `mistral-nemo:12b`, ~7GB). This may take some time depending on your internet connection.*

### Manual Setup

If you prefer to run it locally without Docker:

1.  **Install Ollama:** Download and install from [ollama.ai](https://ollama.ai).
2.  **Pull the model:** Run `ollama pull mistral-nemo:12b`.
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Run the app:**
    ```bash
    streamlit run app/main.py
    ```

## Quick Start

1. Install dependencies from `requirements.txt`
2. Start your local Ollama model
3. Run the app from the repo root:

	```bash
	streamlit run app/main.py
	```

4. Open the app in your browser and upload your first hike

## Privacy and Data Safety

TrailBuddy processes potentially sensitive personal data, including GPS routes, timestamps, and personal notes.

- Keep personal data files out of source control
- Keep generated databases and vector indexes out of source control
- Follow the guidance in [SECURITY.md](SECURITY.md)
- Ignore rules are maintained in [.gitignore](.gitignore)

## Local Data Paths

Runtime data is expected in local-only folders such as:

- data/
- app/data/

These paths are intentionally ignored by Git.

## Before Publishing

1. Verify no personal GPX or database files are tracked
2. Verify no secrets are present in code, docs, or configs
3. If sensitive files were previously committed, rewrite Git history
4. Re-check repository visibility and default branch protections

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

