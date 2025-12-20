# WHO TB Data Insights

A full data pipeline and insights platform for analyzing WHO tuberculosis treatment outcomes. This project provides ETL (Extract, Transform, Load) capabilities and an interactive visual dashboard for exploring TB data across 217 countries, 698 indicators, and 136,000+ data points.

## Features

- **Data Pipeline**: Complete ETL workflow for processing raw WHO TB outcomes data
  - Data extraction and validation
  - Cleaning with imputation logging
  - DB schema transformation (locations, indicators, facts)
  - Bulk database insertion with upsert capabilities

- **Interactive Dashboard**: Streamlit-based web application
  - Filter by WHO region, country, indicator, and year range
  - Dynamic visualizations with Plotly charts
  - Summary statistics (mean, min, max, trends)
  - Responsive design with gradient styling

- **Data Tools**: Import/export functionality
  - Export filtered data to CSV
  - Import pre-processed structured CSVs
  - Full pipeline processing for raw data uploads

## Project Structure

```
TBA/
├── data/
│   ├── raw/              # Raw WHO TB data files
│   ├── cleaned/          # Cleaned data output
│   └── structured/       # Transformed data (locations, indicators, facts)
├── src/
│   ├── data_cleaning/    # Data extraction and cleaning modules
│   ├── transformers/     # DB schema transformation logic
│   ├── insertion/        # Database insertion with upserts
│   └── database/         # SQLAlchemy models and connection
├── scripts/
│   └── run_transformers.py  # ETL pipeline orchestration
├── frontend/
│   ├── Dashboard.py      # Main dashboard (entry point)
│   └── pages/
│       └── Tools.py      # Data import/export tools
├── tests/                # TDD unit tests
└── tb_outcomes.db        # SQLite database
```

## Requirements

- Python 3.13+ (for Streamlit frontend)
- Python 3.14 (for backend/testing)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/IbrahimHaj14/who-tb-data-insights.git
cd TBA
```

2. Install dependencies:
```bash
pip install streamlit plotly sqlalchemy pandas
```

## Running the Frontend

Start the Streamlit dashboard:

```bash
streamlit run frontend/Dashboard.py
```

The application will open in your browser at `http://localhost:8501`


### Navigation

The application has two main pages:

1. **Dashboard** (main page)
   - Filter data by WHO region, country, indicator, and year
   - View interactive line charts showing trends over time
   - See summary statistics (total years, mean, min, max)
   - Access detailed indicator definitions

2. **Tools** (accessible via sidebar)
   - **Export**: Download filtered data as CSV
   - **Import**: Upload structured CSVs or run full ETL pipeline on raw data

## Running the ETL Pipeline (Backend)

### Option 1: Using the Frontend
1. Go to the **Tools** page
2. Select "Raw TB Outcomes CSV (full pipeline)"
3. Upload your raw TB outcomes CSV file
4. Click "Run Full ETL Pipeline"

### Option 2: Command Line

1. Clean raw data:
```bash
python -m src.data_cleaning.data_cleaner
```

2. Transform to schema:
```bash
python scripts/run_transformers.py \
  --cleaned data/cleaned/tb_outcomes_cleaned.csv \
  --dict data/raw/TB_data_dictionary_2025-12-01.csv \
  --output data/structured
```

3. Insert into database:
```bash
python -m src.insertion.insert_structured --dir data/structured
```

## Database Schema

Star schema with fact and dimension tables:

- **Location** (dimension): Countries with ISO codes and WHO regions
- **Indicator** (dimension): TB treatment outcome metrics with definitions
- **TBOutcomeFact** (fact): Time-series data linking locations, indicators, years, and values

## Testing

Run the test suite:
```bash
pytest tests/
```

## Data Source

Data sourced from the WHO Global Tuberculosis Database:
- TB Outcomes: Treatment outcomes by country and year
- Data Dictionary: Indicator definitions and metadata


## Author

Ibrahim Haj
