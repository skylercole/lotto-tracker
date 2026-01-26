# Lotto Tracker

https://skylercole.github.io/lotto-tracker

Minimal, script-driven tracker for lottery data with a lightweight HTML view.

## Features

- Update lottery data via a single Python script.
- Serve a simple static page for quick inspection.
- Keep data in a plain JSON file for portability and versioning.

## Project Structure

- `update.py` - fetches/updates lottery data.
- `lottery_data.json` - current dataset.
- `index.html` - simple viewer.
- `requirements.txt` - Python dependencies.

## Requirements

- Python 3.9+ (recommended)

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

## Usage

Run the update script:

```bash
python update.py
```

Start a local web server:

```bash
python -m http.server 8000
```

Open the page in your browser:

```bash
open http://localhost:8000/
```

## Notes

- Data format is JSON for easy automation and inspection.