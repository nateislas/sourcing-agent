# Sourcing Agent

Deep Research Agent for drug discovery and biomedical entity discovery.

## Setup

### 1. Environment Variables
Copy `.env.example` to `.env` and fill in your API keys:
- `PERPLEXITY_API_KEY`
- `TAVILY_API_KEY`
- `LLAMA_CLOUD_API_KEY`
- `GOOGLE_API_KEY` (for Gemini)
- `TEMPORAL_API_KEY` and `TEMPORAL_NAMESPACE` (for Temporal Cloud)

### 2. Docker Setup
You can run the entire system using Docker:

#### Start the Worker and Frontend
```bash
docker-compose up --build
```

- **Frontend**: Accessible at `http://localhost:8501`
- **Worker**: Runs in the background, listening for Temporal tasks.

#### Run a Research Task via CLI
```bash
docker-compose run worker python backend/run.py "Your research topic"
```

## Local Development (Non-Docker)

### 1. Create a Virtual Environment
```bash
python -m venv env
source env/bin/python  # On macOS/Linux
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Worker
```bash
python backend/worker.py
```

### 4. Run the Streamlit App
```bash
streamlit run frontend/app.py
```

### 5. Run the CLI Runner
```bash
python backend/run.py "Your topic"
```
