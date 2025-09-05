# Crew AI Project

A base Crew AI project for research and reporting using multi-agent systems.

## Setup

1. **Create and activate virtual environment**:
   ```bash
   # Create virtual environment
   python3 -m venv venv
   
   # Activate on macOS/Linux
   source venv/bin/activate
   
   # Activate on Windows
   # venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and add your API keys:
   - `OPENAI_API_KEY` or other LLM provider key
   - `SERPER_API_KEY` for web search capabilities

## Project Structure

```
.
├── config/
│   ├── agents.yaml    # Agent configurations
│   └── tasks.yaml     # Task definitions
├── venv/             # Python virtual environment
├── crew.py           # Main crew implementation
├── main.py           # Entry point
├── requirements.txt  # Python dependencies
├── .env.example      # Environment variables template
├── .gitignore        # Git ignore file
└── README.md         # This file
```

## Usage

Run with default topic:
```bash
python main.py
```

Run with custom topic:
```bash
python main.py "Your Custom Topic Here"
```

Example:
```bash
python main.py "Latest developments in quantum computing"
```

## Components

### Agents
- **Researcher**: Conducts thorough research on the given topic
- **Reporting Analyst**: Creates detailed reports from research findings

### Tasks
- **Research Task**: Gathers relevant information about the topic
- **Reporting Task**: Analyzes research and creates a comprehensive report

## Output

The crew will generate a detailed report saved as `report.md` in the project directory.

## Customization

- Modify `config/agents.yaml` to change agent behaviors
- Update `config/tasks.yaml` to adjust task requirements
- Edit `crew.py` to add new agents or modify the workflow