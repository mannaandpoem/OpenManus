# Dishwasher Workflow System

A professional management system for dishwasher procurement, installation, and contract lifecycle.

## Features

- **End-to-End Workflow**: Manages requests from the initial quotation by sales/client to the final technical acceptance.
- **Supplier Interaction**: Partners can submit quotes directly into the system for selection.
- **Secure Document Management**: Integrated storage for Contracts, Invoices (NFs), and Technical Acceptance forms with path-traversal protection.
- **Contract Lifecycle Tracking**: Automatic notifications for upcoming contract expirations and price adjustment months.
- **Historical Data Import**: Bulk import legacy machine data to ensure full coverage by FY2026.
- **Interactive Dashboard**: Modern web interface to track active workflows and notifications.

## Tech Stack

- **Backend**: FastAPI (Python 3.12)
- **Database**: SQLAlchemy (SQLite)
- **Validation**: Pydantic V2
- **Frontend**: Bootstrap 5 + Vanilla JS
- **Testing**: Pytest + HTTPX

## Getting Started

### Prerequisites

- Python 3.12+

### Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   python -m uvicorn app.main:app --reload
   ```

3. Access the system:
   - **Dashboard**: [http://localhost:8000/dashboard](http://localhost:8000/dashboard)
   - **API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)

## API Overview

The API is organized into three main sections:

### 1. Requests (`/api/requests`)
- `POST /`: Create a new request.
- `GET /`: List all requests.
- `POST /{id}/quotes`: Submit a quote for a request.
- `POST /{id}/select-quote`: Select the winning quote.
- `GET /notifications/upcoming`: List requests requiring attention (expirations/adjustments).
- `POST /import-history`: Bulk import historical data.

### 2. Partners (`/api/partners`)
- `POST /`: Register a new supplier.
- `GET /`: List registered partners.

### 3. Documents (`/api/documents`)
- `POST /{request_id}/upload`: Upload a document (Contract, Invoice, etc.).
- `GET /{request_id}`: List documents for a request.
- `GET /download/{document_id}`: Download a specific document.

## Workflow Stages

1. `quotation`: Initial request created.
2. `supplier_interaction`: Partners submit quotes.
3. `selection`: Winning quote is selected.
4. `contracting`: Contract is uploaded.
5. `installation`: Invoice (NF) is uploaded.
6. `technical_acceptance`: Final acceptance document is uploaded.
7. `completed`: Workflow finished.

## Running Tests

Execute the test suite using `pytest`:
```bash
pytest
```

## Security & Reliability

- **Path Sanitization**: Uploaded files are renamed using UUIDs to prevent directory traversal and filename collisions.
- **Structured Logging**: Comprehensive logs for all major state transitions.
- **Circular Dependency Fix**: Database models use `use_alter` for complex foreign key relationships.
- **Pydantic V2 Compliance**: Uses the latest validation patterns.
