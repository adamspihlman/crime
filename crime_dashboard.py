import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
import geopandas as gpd
from shapely.geometry import Point

st.set_page_config(
    page_title="Chicago Crime Dashboard",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    try:
        df = pd.read_csv('data.csv')
        
        df['DATE  OF OCCURRENCE'] = pd.to_datetime(df['DATE  OF OCCURRENCE'], errors='coerce')
        
        df.columns = df.columns.str.strip()
        
        df['Year'] = df['DATE  OF OCCURRENCE'].dt.year
        df['Month'] = df['DATE  OF OCCURRENCE'].dt.month
        df['Day'] = df['DATE  OF OCCURRENCE'].dt.day
        df['Hour'] = df['DATE  OF OCCURRENCE'].dt.hour
        df['Day_of_Week'] = df['DATE  OF OCCURRENCE'].dt.day_name()
        
        df = df.dropna(subset=['DATE  OF OCCURRENCE'])

        neighborhoods_url = "https://data.cityofchicago.org/resource/igwz-8jzy.geojson"
        neighborhoods_gdf = gpd.read_file(neighborhoods_url)

        print(neighborhoods_gdf.head())

        df = df.dropna(subset=['LATITUDE', 'LONGITUDE'])
        geometry = [Point(xy) for xy in zip(df['LONGITUDE'], df['LATITUDE'])]
        crimes_gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")

        print(crimes_gdf.head())

        df = gpd.sjoin(crimes_gdf, neighborhoods_gdf, how="left", predicate="within")

        print(df.head())

        df = df.rename(columns={'community': 'neighborhood'})

        print('Pre column drops')

        df = df.drop(columns=[
            'DOMESTIC', 'BEAT', 'WARD', 'geometry', 'index_right', 
            'Month', 'Day', 'Year', 'Hour', 'Day_of_Week', 
            'shape_area', 'area_numbe', 'area_num_1', 'shape_len', 
            'LOCATION', 'X COORDINATE', 'Y COORDINATE', 'IUCR'])
                
        print('Post column drops')
        return df


    except Exception as e:
            st.error(f"Error loading data: {e}")
            return None

def main():
    st.markdown('<h1 class="main-header">🚨 Chicago Crime Dashboard</h1>', unsafe_allow_html=True)
    
    df = load_data()
    if df is None:
        st.stop()
    
    st.sidebar.header("🔍 Filters")
    
    min_date = df['DATE  OF OCCURRENCE'].min().date()
    max_date = df['DATE  OF OCCURRENCE'].max().date()
    
    date_range = st.sidebar.date_input(
        "Select Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        df_filtered = df[
            (df['DATE  OF OCCURRENCE'].dt.date >= start_date) & 
            (df['DATE  OF OCCURRENCE'].dt.date <= end_date)
        ]
    else:
        df_filtered = df
    
    crime_types = sorted(df_filtered['PRIMARY DESCRIPTION'].unique())
    selected_crimes = st.sidebar.multiselect(
        "Select Crime Types",
        options=crime_types,
        default=crime_types[:5] if len(crime_types) > 5 else crime_types
    )
    
    if selected_crimes:
        df_filtered = df_filtered[df_filtered['PRIMARY DESCRIPTION'].isin(selected_crimes)]
    
    arrest_filter = st.sidebar.selectbox(
        "Arrest Status",
        options=["All", "Arrest Made", "No Arrest"]
    )
    
    if arrest_filter == "Arrest Made":
        df_filtered = df_filtered[df_filtered['ARREST'] == 'Y']
    elif arrest_filter == "No Arrest":
        df_filtered = df_filtered[df_filtered['ARREST'] == 'N']
    
    st.markdown("---")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Crimes",
            value=f"{len(df_filtered):,}",
            delta=f"{len(df_filtered) - len(df):,}" if len(df_filtered) != len(df) else None
        )
    
    with col2:
        arrest_rate = (df_filtered['ARREST'] == 'Y').mean() * 100
        st.metric(
            label="Arrest Rate",
            value=f"{arrest_rate:.1f}%"
        )
    
    with col3:
        unique_crimes = df_filtered['PRIMARY DESCRIPTION'].nunique()
        st.metric(
            label="Crime Types",
            value=unique_crimes
        )
    
    with col4:
        if not df_filtered.empty:
            avg_lat = df_filtered['LATITUDE'].mean()
            avg_lon = df_filtered['LONGITUDE'].mean()
            st.metric(
                label="Avg Location",
                value=f"({avg_lat:.3f}, {avg_lon:.3f})"
            )
    
    st.markdown("---")

    st.subheader("📅 Crimes by Neighborhood")
    neighborhood_counts = df_filtered['neighborhood'].value_counts().sort_values(ascending=False)
    
    fig_line = px.line(
        x=neighborhood_counts.index,
        y=neighborhood_counts.values,
        title="Crimes by Neighborhood",
        labels={'x': 'Neighborhood', 'y': 'Number of Crimes'}
    )
    fig_line.update_layout(height=400)
    st.plotly_chart(fig_line, use_container_width=True)
    
    st.subheader("🗺️ Crime Map")
    
    map_sample_size = min(5000, len(df_filtered))
    df_map = df_filtered.sample(n=map_sample_size, random_state=42)
    
    fig_map = px.scatter_mapbox(
        df_map,
        lat='LATITUDE',
        lon='LONGITUDE',
        color='PRIMARY DESCRIPTION',
        hover_data=['DATE  OF OCCURRENCE', 'BLOCK', 'ARREST'],
        zoom=10,
        height=500,
        title=f"Crime Locations (Sample of {map_sample_size:,} records)"
    )
    fig_map.update_layout(
        mapbox_style="open-street-map",
        margin={"r": 0, "t": 0, "l": 0, "b": 0}
    )
    st.plotly_chart(fig_map, use_container_width=True)
    
    st.subheader("📋 Crime Data Table")
    
    page_size = st.selectbox("Records per page", [50, 100, 200, 500], index=1)
    
    total_pages = len(df_filtered) // page_size + (1 if len(df_filtered) % page_size > 0 else 0)
    
    if total_pages > 1:
        page = st.number_input("Page", min_value=1, max_value=total_pages, value=1)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        df_display = df_filtered.iloc[start_idx:end_idx]
    else:
        df_display = df_filtered
    
    st.dataframe(
        df_display,
        use_container_width=True,
        height=400
    )
    
    csv = df_filtered.to_csv(index=False)
    st.download_button(
        label="📥 Download Filtered Data as CSV",
        data=csv,
        file_name=f"chicago_crimes_filtered_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )
    
    st.markdown("---")
    st.markdown(
        f"<div style='text-align: center; color: #666;'>"
        f"Data loaded: {len(df):,} total records | "
        f"Filtered: {len(df_filtered):,} records | "
        f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        f"</div>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
