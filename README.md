# Morai - GenAI Press Review Service (non-functional, under implementation)

This project aggregates and processes RSS feeds to generate a press review using AI models.
It supports the selection between local (Ollama) and external (Open-Webui) models via configurable endpoints.

# Python Scheduled Tasks

This project provides a framework for scheduling tasks to fetch URLs and correlate events from the fetched articles. It is designed to be modular, allowing for easy extension and maintenance.

## Project Structure

```
python-scheduled-tasks
├── feeds                # Directory containing feed files with URLs
├── src
│   ├── main.py         # Entry point of the application
│   └── tasks
│       ├── __init__.py # Initializes the tasks module
│       ├── fetch_task.py # Defines the FetchTask class for URL fetching
│       └── event_correlator.py # Defines the EventCorrelator class for event analysis
├── requirements.txt     # Lists project dependencies
└── README.md            # Project documentation
```

## Setup Instructions

1. **Clone the repository:**
   ```
   git clone <repository-url>
   cd python-scheduled-tasks
   ```

2. **Install dependencies:**
   Make sure you have Python installed, then run:
   ```
   pip install -r requirements.txt
   ```

## Usage

To start the application, run the following command:
```
python src/main.py
```

This will initialize the task scheduler, fetch URLs from the specified feed files, and begin correlating events from the fetched articles.

## Task Descriptions

- **FetchTask**: This task is responsible for fetching URLs at scheduled intervals. It handles the fetching process, manages responses, and ensures that tasks are executed as planned.

- **EventCorrelator**: This task analyzes the articles fetched by the FetchTask. It extracts relevant events and provides insights based on the content of the articles.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.