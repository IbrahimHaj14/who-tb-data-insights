"""Base transformer class with shared utilities for all transformers."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, List, Dict, Any, Optional

import pandas as pd
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class BaseTransformer(ABC):
    """Abstract base class for transforming cleaned data into SDOs.
    
    Provides common utilities:
    - Loading and validating DataFrames
    - Column normalization
    - Chunking/batching
    - Error collection
    - Output writing (CSV/JSONL)
    """

    def __init__(self, output_dir: str = "data/structured"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.issues: List[Dict[str, Any]] = []
        self.records_in = 0
        self.records_out = 0

    @abstractmethod
    def transform(self, df: pd.DataFrame) -> Iterable[BaseModel]:
        """Transform cleaned DataFrame into stream of SDO instances.
        
        Args:
            df: Cleaned pandas DataFrame
            
        Yields:
            Pydantic BaseModel instances (LocationRecord, IndicatorRecord, OutcomeFactRecord)
        """
        pass

    @abstractmethod
    def output_path(self) -> Path:
        """Return the target output path for this transformer."""
        pass

    def load_df(
        self,
        path: str,
        na_values: Optional[List[str]] = None,
        dtype: Optional[str] = None,
    ) -> pd.DataFrame:
        """Load a CSV file with standard NA handling.
        
        Args:
            path: Path to CSV file
            na_values: List of strings to treat as NA
            dtype: Data type for all columns (default: infer)
            
        Returns:
            Loaded DataFrame
        """
        if na_values is None:
            na_values = ["", "NA", "N/A", "null", "NULL", " "]

        logger.info("Loading %s", path)
        df = pd.read_csv(path, na_values=na_values, keep_default_na=True, dtype=dtype)
        self.records_in = len(df)
        logger.info("Loaded %d rows", self.records_in)
        return df

    def clean_cols(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names: lowercase, strip whitespace.
        
        Args:
            df: Input DataFrame
            
        Returns:
            DataFrame with cleaned column names
        """
        df.columns = [col.strip().lower() for col in df.columns]
        return df

    def clean_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Trim whitespace from string columns.
        
        Args:
            df: Input DataFrame
            
        Returns:
            DataFrame with trimmed string values
        """
        for col in df.select_dtypes(include="object").columns:
            df[col] = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)
        return df

    def chunk(self, iterable: Iterable, size: int = 5000) -> Iterable[List]:
        """Yield chunks of items from an iterable.
        
        Args:
            iterable: Iterable to chunk
            size: Chunk size (default: 5000)
            
        Yields:
            Lists of items, each of max size `size`
        """
        chunk = []
        for item in iterable:
            chunk.append(item)
            if len(chunk) >= size:
                yield chunk
                chunk = []
        if chunk:
            yield chunk

    def write_output(
        self,
        records: List[BaseModel],
        orient: str = "records",
        include_index: bool = False,
    ) -> str:
        """Write SDO records to CSV file.
        
        Args:
            records: List of Pydantic BaseModel instances
            orient: Pandas orient parameter (default: 'records')
            include_index: Include DataFrame index (default: False)
            
        Returns:
            Path to written file
        """
        if not records:
            logger.warning("No records to write")
            return str(self.output_path())

        # Convert records to dictionaries
        data = [r.dict() for r in records]
        df = pd.DataFrame(data)
        
        path = self.output_path()
        logger.info("Writing %d records to %s", len(records), path)
        df.to_csv(path, index=include_index)
        self.records_out = len(records)
        return str(path)

    def log_issue(self, message: str, sample: Optional[Any] = None):
        """Log an issue encountered during transformation.
        
        Args:
            message: Description of the issue
            sample: Sample row or data that triggered the issue
        """
        issue = {"message": message}
        if sample is not None:
            issue["sample"] = str(sample)[:200] 
        self.issues.append(issue)
        logger.warning(message)

    def run(self, input_path: str) -> Dict[str, Any]:
        """Execute the full transformation pipeline.
        
        Steps:
        1. Load cleaned CSV
        2. Normalize columns
        3. Transform to SDOs
        4. Validate via Pydantic
        5. Write output
        
        Args:
            input_path: Path to cleaned CSV file
            
        Returns:
            Summary dict with counts and issues
        """
        logger.info("Starting %s", self.__class__.__name__)
        
        # Load and clean
        df = self.load_df(input_path)
        df = self.clean_cols(df)
        df = self.clean_values(df)
        
        # Transform
        valid_records = []
        for record in self.transform(df):
            try:
                # Validate Pydantic model
                if isinstance(record, dict):
                    record = self._dict_to_model(record)
                else:
                    record.validate(record)  # Trigger validation
                valid_records.append(record)
            except ValidationError as e:
                self.log_issue(f"Validation error: {e.errors()[0] if e.errors() else e}", record)
            except Exception as e:
                self.log_issue(f"Transform error: {e}", record)
        
        # Write outputs
        output_file = self.write_output(valid_records)
        
        summary = {
            "transformer": self.__class__.__name__,
            "input_file": input_path,
            "output_file": output_file,
            "records_in": self.records_in,
            "records_out": len(valid_records),
            "issues_count": len(self.issues),
            "issues": self.issues[:10] if self.issues else [],  
        }
        
        logger.info("Completed %s: %d -> %d records", self.__class__.__name__, self.records_in, len(valid_records))
        return summary

    def _dict_to_model(self, d: Dict[str, Any]):
        """Override in subclasses to convert dict to appropriate SDO model."""
        return d
