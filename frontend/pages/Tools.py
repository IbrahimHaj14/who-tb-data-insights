import streamlit as st
import pandas as pd
from sqlalchemy import select
from src.database.connection import SessionLocal
from src.database.models_dimension import Location, Indicator
from src.database.models_fact import TBOutcomeFact
from src.insertion.insert_structured import upsert_locations, upsert_indicators, insert_outcome_facts, read_csv, run_insertion
from src.data_cleaning.data_cleaner import clean_tb_outcomes
from scripts.run_transformers import run_pipeline
from io import StringIO
import os
from pathlib import Path
import tempfile
import logging
import shutil

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


st.set_page_config(page_title="Data Tools", page_icon="🛠️", layout="wide")

# Custom CSS for consistent styling
st.markdown("""
    <style>
    .main {
        background-color: #f5f7fa;
    }
    h1 {
        color: #2d3748;
        font-weight: 700;
    }
    h2 {
        color: #4a5568;
        font-weight: 600;
    }
    .tool-card {
        background: white;
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# Title
st.markdown("""
    <div style='background: linear-gradient(135deg, #ffffff 0%, #f0f0f0 100%); 
                padding: 30px; border-radius: 15px; margin-bottom: 30px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
        <h1 style='color: #2d3748; margin: 0; font-size: 42px;'>🛠️ Data Tools</h1>
        <p style='color: #4a5568; margin: 10px 0 0 0; font-size: 18px;'>
            Import and export TB outcomes data
        </p>
    </div>
    """, unsafe_allow_html=True)

# Export Section
st.markdown("<div class='tool-card'>", unsafe_allow_html=True)
st.markdown("## 📤 Export Data to CSV")
st.markdown("Export TB outcomes data from the database to CSV format.")

# Export filters
col1, col2 = st.columns(2)

with col1:
    export_type = st.selectbox(
        "Select data to export",
        ["All Data", "By Country", "By Indicator", "By Year Range", "Custom Query"]
    )

with col2:
    include_definitions = st.checkbox("Include indicator definitions", value=True)

# Additional filters based on export type
if export_type == "By Country":
    with SessionLocal() as session:
        countries = session.execute(
            select(Location.country, Location.iso3).order_by(Location.country)
        ).all()
    country_options = {f"{c.country} ({c.iso3})": c.iso3 for c in countries}
    selected_country = st.selectbox("Select Country", list(country_options.keys()))
    filter_iso3 = country_options[selected_country]
    
elif export_type == "By Indicator":
    with SessionLocal() as session:
        indicators = session.execute(
            select(Indicator.variable_name).order_by(Indicator.variable_name)
        ).scalars().all()
    selected_indicator = st.selectbox("Select Indicator", indicators)
    
elif export_type == "By Year Range":
    year_range = st.slider("Select Year Range", min_value=2000, max_value=2023, value=(2010, 2023))

# Export button
if st.button("📥 Export to CSV", type="primary"):
    with st.spinner("Exporting data..."):
        with SessionLocal() as session:
            query = select(
                Location.country,
                Location.iso3,
                Location.who_region,
                Indicator.variable_name,
                Indicator.definition,
                TBOutcomeFact.year,
                TBOutcomeFact.value
            ).join(Location, TBOutcomeFact.location_id == Location.id)\
             .join(Indicator, TBOutcomeFact.indicator_id == Indicator.id)
            
            # Apply filters
            if export_type == "By Country":
                query = query.where(Location.iso3 == filter_iso3)
            elif export_type == "By Indicator":
                query = query.where(Indicator.variable_name == selected_indicator)
            elif export_type == "By Year Range":
                query = query.where(TBOutcomeFact.year >= year_range[0])\
                             .where(TBOutcomeFact.year <= year_range[1])
            
            results = session.execute(query).all()
        
        if results:
            # Convert to DataFrame
            df = pd.DataFrame([
                {
                    "Country": r.country,
                    "ISO3": r.iso3,
                    "WHO Region": r.who_region,
                    "Indicator": r.variable_name,
                    "Definition": r.definition if include_definitions else None,
                    "Year": r.year,
                    "Value": r.value
                }
                for r in results
            ])
            
            # Remove definition column if not needed
            if not include_definitions:
                df = df.drop(columns=["Definition"])
            
            # Convert to CSV
            csv = df.to_csv(index=False)
            
            # Download button
            st.success(f"✅ Exported {len(df)} records")
            st.download_button(
                label="💾 Download CSV",
                data=csv,
                file_name=f"tb_outcomes_export_{export_type.lower().replace(' ', '_')}.csv",
                mime="text/csv"
            )
            
            # Preview
            st.markdown("### Preview (first 10 rows)")
            st.dataframe(df.head(10), use_container_width=True)
        else:
            st.warning("No data found for the selected filters.")

st.markdown("</div>", unsafe_allow_html=True)

# Import Section
st.markdown("<div class='tool-card'>", unsafe_allow_html=True)
st.markdown("## 📥 Import Data from CSV")
st.markdown("Upload a CSV file to import TB outcomes data into the database.")

st.info("ℹ️ Upload structured CSV files (already transformed) or raw TB outcomes data to process through the full ETL pipeline")

upload_type = st.radio(
    "Upload type",
    ["Structured CSVs (pre-processed)", "Raw TB Outcomes CSV (full pipeline)"],
    help="Structured CSVs are ready for direct insertion. Raw data will be cleaned, transformed, and inserted automatically."
)

if upload_type == "Structured CSVs (pre-processed)":
    col1, col2, col3 = st.columns(3)
    
    with col1:
        locations_file = st.file_uploader("locations.csv (optional)", type="csv", key="loc")
    with col2:
        indicators_file = st.file_uploader("indicators.csv (optional)", type="csv", key="ind")
    with col3:
        facts_file = st.file_uploader("outcome_facts.csv (optional)", type="csv", key="facts")
    
    if locations_file or indicators_file or facts_file:
        # Preview uploaded files
        if locations_file:
            st.markdown("#### Locations Preview")
            loc_df = pd.read_csv(locations_file)
            st.dataframe(loc_df.head(5), use_container_width=True)
            locations_file.seek(0)  # Reset file pointer
        
        if indicators_file:
            st.markdown("#### Indicators Preview")
            ind_df = pd.read_csv(indicators_file)
            st.dataframe(ind_df.head(5), use_container_width=True)
            indicators_file.seek(0)
        
        if facts_file:
            st.markdown("#### Facts Preview")
            facts_df = pd.read_csv(facts_file)
            st.dataframe(facts_df.head(5), use_container_width=True)
            st.info(f"📊 {len(facts_df):,} fact records ready to import")
            facts_file.seek(0)
        
        # Import options
        col1, col2 = st.columns(2)
        with col1:
            import_mode = st.radio(
                "Import mode",
                ["Append (upsert dimensions, add facts)", "Replace facts (clear facts table first)"],
                help="Append uses upsert for dimensions. Replace clears only the facts table."
            )
        
        with col2:
            batch_size = st.number_input("Batch size for facts", min_value=100, max_value=10000, value=5000)
        
        # Import button
        if st.button("📤 Import to Database", type="primary"):
            with st.spinner("Importing data using backend pipeline..."):
                try:
                    with SessionLocal() as session:
                        # Clear facts if replace mode
                        if "Replace" in import_mode:
                            count = session.query(TBOutcomeFact).count()
                            session.query(TBOutcomeFact).delete()
                            session.commit()
                            st.info(f"🗑️ Cleared {count:,} existing fact records")
                        
                        # Process locations using existing backend function
                        iso_to_id = {}
                        if locations_file:
                            loc_df = pd.read_csv(locations_file)
                            loc_df.columns = [c.strip().lower() for c in loc_df.columns]
                            iso_to_id = upsert_locations(session, loc_df)
                            st.success(f"✅ Upserted {len(iso_to_id)} locations")
                        else:
                            # Get existing locations for facts FK resolution
                            existing_locs = session.execute(select(Location.iso3, Location.id)).all()
                            iso_to_id = {loc.iso3: loc.id for loc in existing_locs}
                        
                        # Process indicators using existing backend function
                        var_to_id = {}
                        if indicators_file:
                            ind_df = pd.read_csv(indicators_file)
                            ind_df.columns = [c.strip().lower() for c in ind_df.columns]
                            var_to_id = upsert_indicators(session, ind_df)
                            st.success(f"✅ Upserted {len(var_to_id)} indicators")
                        else:
                            # Get existing indicators for facts FK resolution
                            existing_inds = session.execute(select(Indicator.variable_name, Indicator.id)).all()
                            var_to_id = {ind.variable_name: ind.id for ind in existing_inds}
                        
                        # Process facts using existing backend function
                        if facts_file:
                            facts_df = pd.read_csv(facts_file)
                            facts_df.columns = [c.strip().lower() for c in facts_df.columns]
                            inserted = insert_outcome_facts(session, facts_df, iso_to_id, var_to_id, batch_size=batch_size)
                            st.success(f"✅ Inserted {inserted:,} fact records")
                        
                        st.balloons()
                        st.success("🎉 Import completed successfully!")
                
                except Exception as e:
                    st.error(f" Import failed: {str(e)}")
                    logger.exception("Import error")

else:
    # Raw TB outcomes file upload - full pipeline
    uploaded_file = st.file_uploader("Upload raw TB outcomes CSV", type="csv")
    dict_file = st.file_uploader("Upload TB data dictionary CSV (optional)", type="csv", key="dict")
    
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        st.markdown("### Preview of uploaded data")
        st.dataframe(df.head(10), use_container_width=True)
        st.info(f"📊 {len(df):,} rows, {len(df.columns)} columns")
        
        # Pipeline options
        col1, col2 = st.columns(2)
        with col1:
            clear_existing = st.checkbox("Clear existing data before import", value=False)
        with col2:
            batch_size = st.number_input("Batch size for facts", min_value=100, max_value=10000, value=5000)
        
        if st.button("🔄 Run Full ETL Pipeline", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmppath = Path(tmpdir)
                    
                    # Save uploaded files
                    raw_file = tmppath / "raw" / "tb_outcomes.csv"
                    raw_file.parent.mkdir(parents=True, exist_ok=True)
                    df.to_csv(raw_file, index=False)
                    
                    # Save data dictionary if provided, otherwise use default
                    dict_path = "data/raw/TB_data_dictionary_2025-12-01.csv"
                    if dict_file is not None:
                        dict_df = pd.read_csv(dict_file)
                        dict_path = tmppath / "raw" / "TB_data_dictionary.csv"
                        dict_df.to_csv(dict_path, index=False)
                    
                    # Clean
                    status_text.text("Step 1/4: Cleaning data...")
                    progress_bar.progress(0.25)
                    
                    cleaned_dir = tmppath / "cleaned"
                    cleaned_dir.mkdir(parents=True, exist_ok=True)
                    
                    clean_result = clean_tb_outcomes(
                        raw_path=str(raw_file),
                        dict_path=str(dict_path),
                        out_dir=str(cleaned_dir)
                    )
                    st.success(f"✅ Cleaned: {clean_result.get('rows_after_cleaning', 0):,} rows")
                    
                    #  Transform
                    status_text.text("Step 2/4: Transforming data...")
                    progress_bar.progress(0.50)
                    
                    structured_dir = tmppath / "structured"
                    structured_dir.mkdir(parents=True, exist_ok=True)
                    
                    cleaned_csv = cleaned_dir / "tb_outcomes_cleaned.csv"
                    
                    transform_result = run_pipeline(
                        cleaned_csv=str(cleaned_csv),
                        dict_csv=str(dict_path),
                        output_dir=str(structured_dir)
                    )
                    
                    st.success(f"✅ Transformed: {transform_result['locations'].get('records_out', 0)} locations, "
                              f"{transform_result['indicators'].get('records_out', 0)} indicators, "
                              f"{transform_result['facts'].get('records_out', 0)} facts")
                    
                    # Create database tables and clear data if requested
                    status_text.text("Step 3/4: Preparing database...")
                    progress_bar.progress(0.65)
                    
                    from src.database.models_base import Base
                    from src.database.connection import engine
                    
                    # Ensure tables exist
                    Base.metadata.create_all(bind=engine)
                    
                    if clear_existing:
                        with SessionLocal() as session:
                            fact_count = session.query(TBOutcomeFact).count()
                            session.query(TBOutcomeFact).delete()
                            session.commit()
                            st.info(f"🗑️ Cleared {fact_count:,} existing fact records")
                    
                    # Insert
                    status_text.text("Step 4/4: Inserting into database...")
                    progress_bar.progress(0.80)
                    
                    run_insertion(structured_dir=structured_dir)
                    
                    progress_bar.progress(1.0)
                    status_text.text("✅ Pipeline completed!")
                    
                
                    st.success("Full ETL pipeline completed successfully!")
                    
                    # Show summary
                    with st.expander("📋 Pipeline Summary"):
                        st.json({
                            "cleaning": clean_result,
                            "transformation": {
                                "locations": transform_result['locations'].get('records_out', 0),
                                "indicators": transform_result['indicators'].get('records_out', 0),
                                "facts": transform_result['facts'].get('records_out', 0)
                            }
                        })
            
            except Exception as e:
                st.error(f"Pipeline failed: {str(e)}")
                logger.exception("Pipeline error")
                status_text.text("Pipeline failed")
                progress_bar.empty()

st.markdown("</div>", unsafe_allow_html=True)


