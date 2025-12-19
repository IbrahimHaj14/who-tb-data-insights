import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import select
from src.database.connection import SessionLocal
from src.database.models_dimension import Location, Indicator
from src.database.models_fact import TBOutcomeFact


st.set_page_config(page_title="TB Outcomes Dashboard", page_icon="🏥", layout="wide")

# Custom CSS for better styling
st.markdown("""
    <style>
    .main {
        background-color: #f5f7fa;
    }
    .stMetric {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .metric-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 15px;
        color: white;
        margin-bottom: 20px;
    }
    .definition-box {
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        padding: 25px;
        border-radius: 15px;
        color: #1e3a5f;
        font-size: 18px;
        font-weight: 500;
        margin: 20px 0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .definition-label {
        font-size: 14px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
        opacity: 0.9;
        margin-bottom: 10px;
    }
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
    }
    h1 {
        color: #2d3748;
        font-weight: 700;
    }
    h2 {
        color: #4a5568;
        font-weight: 600;
    }
    </style>
    """, unsafe_allow_html=True)

# Title with white/gray background
st.markdown("""
    <div style='background: linear-gradient(135deg, #ffffff 0%, #f0f0f0 100%); 
                padding: 30px; border-radius: 15px; margin-bottom: 30px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
        <h1 style='color: #2d3748; margin: 0; font-size: 42px;'>🏥 TB Outcomes Data Insights</h1>
        <p style='color: #4a5568; margin: 10px 0 0 0; font-size: 18px;'>
            Explore WHO tuberculosis treatment outcomes by country, indicator, and year
        </p>
    </div>
    """, unsafe_allow_html=True)

# Sidebar filters
st.sidebar.header("Filters")

# Load data for filters
@st.cache_data
def load_filter_options():
    with SessionLocal() as session:
        countries = session.execute(
            select(Location.country, Location.iso3, Location.who_region).order_by(Location.country)
        ).all()
        # WHO regions
        regions = session.execute(
            select(Location.who_region)
            .where(Location.who_region.isnot(None))
            .distinct()
            .order_by(Location.who_region)
        ).scalars().all()
        # Filter indicators that have data in facts table
        indicators = session.execute(
            select(Indicator.variable_name, Indicator.definition)
            .join(TBOutcomeFact, Indicator.id == TBOutcomeFact.indicator_id)
            .distinct()
            .order_by(Indicator.variable_name)
        ).all()
    return countries, regions, indicators

@st.cache_data
def load_countries_for_region(region: str):
    """Load countries for the selected WHO region."""
    if region == "All Regions":
        with SessionLocal() as session:
            countries = session.execute(
                select(Location.country, Location.iso3, Location.who_region).order_by(Location.country)
            ).all()
        return countries
    else:
        with SessionLocal() as session:
            countries = session.execute(
                select(Location.country, Location.iso3, Location.who_region)
                .where(Location.who_region == region)
                .order_by(Location.country)
            ).all()
        return countries

@st.cache_data
def load_indicators_for_country(iso3: str):
    """Load only indicators that have data for the selected country."""
    with SessionLocal() as session:
        indicators = session.execute(
            select(Indicator.variable_name, Indicator.definition)
            .join(TBOutcomeFact, Indicator.id == TBOutcomeFact.indicator_id)
            .join(Location, TBOutcomeFact.location_id == Location.id)
            .where(Location.iso3 == iso3)
            .distinct()
            .order_by(Indicator.variable_name)
        ).all()
    return indicators

countries, regions, _ = load_filter_options()


# WHO Region selector
region_options = ["All Regions"] + list(regions)
selected_region = st.sidebar.selectbox(
    "🌍 WHO Region",
    options=region_options,
    index=0
)

# Filter countries by selected region
filtered_countries = load_countries_for_region(selected_region)

# Country selector
country_options = {f"{c.country} ({c.iso3})": c.iso3 for c in filtered_countries}
selected_country_label = st.sidebar.selectbox(
    "🌎 Select Country",
    options=list(country_options.keys()),
    index=0
)
selected_country_iso3 = country_options[selected_country_label]

# Load indicators for selected country
indicators = load_indicators_for_country(selected_country_iso3)

# Indicator selector
indicator_options = {f"{i.variable_name}": i.variable_name for i in indicators}
selected_indicator = st.sidebar.selectbox(
    "📊 Select Indicator",
    options=list(indicator_options.keys()) if indicator_options else ["No data available"],
    index=0 if indicator_options else None,
    disabled=not indicator_options
)

# Year range
year_range = st.sidebar.slider(
    "📅 Year Range",
    min_value=2000,
    max_value=2023,
    value=(2010, 2023)
)

# Query data
@st.cache_data
def query_data(iso3: str, variable: str, year_min: int, year_max: int):
    with SessionLocal() as session:
        query = (
            select(
                TBOutcomeFact.year,
                TBOutcomeFact.value,
                Location.country,
                Location.iso3,
                Indicator.variable_name,
                Indicator.definition
            )
            .join(Location, TBOutcomeFact.location_id == Location.id)
            .join(Indicator, TBOutcomeFact.indicator_id == Indicator.id)
            .where(Location.iso3 == iso3)
            .where(Indicator.variable_name == variable)
            .where(TBOutcomeFact.year >= year_min)
            .where(TBOutcomeFact.year <= year_max)
            .order_by(TBOutcomeFact.year)
        )
        results = session.execute(query).all()
    
    if not results:
        return pd.DataFrame()
    
    df = pd.DataFrame([
        {
            "Year": r.year,
            "Value": r.value,
            "Country": r.country,
            "ISO3": r.iso3,
            "Indicator": r.variable_name,
            "Definition": r.definition
        }
        for r in results
    ])
    return df

# Fetch data
if indicator_options and selected_indicator != "No data available":
    df = query_data(selected_country_iso3, selected_indicator, year_range[0], year_range[1])
else:
    df = pd.DataFrame()

# Display
if not df.empty:
    # Indicator title
    st.markdown(f"<h1 style='color: #2d3748; margin-bottom: 10px;'>📊 {selected_indicator}</h1>", unsafe_allow_html=True)
    
    # Indicator definition in prominent styled box
    st.markdown(f"""
        <div class='definition-box'>
            <div class='definition-label'>📖 INDICATOR DEFINITION</div>
            <div style='font-size: 20px; line-height: 1.6;'>{df.iloc[0]["Definition"]}</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Summary stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 12px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
                <div style='color: rgba(255,255,255,0.9); font-size: 14px; font-weight: 600;'>📅 TOTAL YEARS</div>
                <div style='color: white; font-size: 36px; font-weight: 700; margin-top: 10px;'>{len(df)}</div>
            </div>
            """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 20px; border-radius: 12px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
                <div style='color: rgba(255,255,255,0.9); font-size: 14px; font-weight: 600;'>📈 MEAN</div>
                <div style='color: white; font-size: 36px; font-weight: 700; margin-top: 10px;'>{df['Value'].mean():.2f}</div>
            </div>
            """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); padding: 20px; border-radius: 12px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
                <div style='color: rgba(255,255,255,0.9); font-size: 14px; font-weight: 600;'>📉 MIN</div>
                <div style='color: white; font-size: 36px; font-weight: 700; margin-top: 10px;'>{df['Value'].min():.2f}</div>
            </div>
            """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); padding: 20px; border-radius: 12px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
                <div style='color: rgba(255,255,255,0.9); font-size: 14px; font-weight: 600;'>🔝 MAX</div>
                <div style='color: white; font-size: 36px; font-weight: 700; margin-top: 10px;'>{df['Value'].max():.2f}</div>
            </div>
            """, unsafe_allow_html=True)
    
    # Line chart with enhanced styling
    st.markdown("<h2 style='color: #4a5568; margin-top: 30px;'>📈 Trend Over Time</h2>", unsafe_allow_html=True)
    fig = px.line(
        df,
        x="Year",
        y="Value",
        title=f"{selected_indicator} - {selected_country_label}",
        markers=True,
        template="plotly_white"
    )
    fig.update_traces(
        line=dict(color='#667eea', width=3),
        marker=dict(size=10, color='#764ba2', line=dict(width=2, color='white'))
    )
    fig.update_layout(
        xaxis_title="Year",
        yaxis_title="Value",
        hovermode="x unified",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(size=14),
        title_font_size=20,
        title_font_color='#2d3748'
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Data table
    with st.expander("📋 View Data Table"):
        st.dataframe(df[["Year", "Value"]], use_container_width=True)
else:
    st.warning("No data found for the selected filters. Try adjusting your selection.")


st.sidebar.markdown("---")
st.sidebar.caption("Data source: WHO TB Outcomes")
