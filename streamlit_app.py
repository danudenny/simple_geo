import streamlit as st
import geopandas as gpd
import json
from shapely.geometry import shape, mapping, Polygon, MultiPolygon
from shapely import wkt
import visvalingamwyatt as vw
import tempfile
import os
from io import StringIO

# Reusing the functions you provided
def count_polygon_coordinates(polygon):
    if isinstance(polygon, Polygon):
        return len(polygon.exterior.coords)
    elif isinstance(polygon, MultiPolygon):
        return sum(len(poly.exterior.coords) for poly in polygon.geoms)
    return 0

def fix_vertices(geom_input, max_vertices=39):
    try:
        if isinstance(geom_input, str):
            geom = wkt.loads(geom_input)
        elif isinstance(geom_input, (Polygon, MultiPolygon)):
            geom = geom_input
        else:
            return geom_input

        num_vertices = count_polygon_coordinates(geom)
        if num_vertices <= max_vertices:
            return geom_input

        geom_mapping = mapping(geom)
        simplified_geom = vw.simplify_geometry(geom_mapping, number=max_vertices)
        simplified_shapely_geom = shape(simplified_geom)

        if isinstance(geom_input, str):
            return simplified_shapely_geom.wkt
        else:
            return simplified_shapely_geom

    except Exception as e:
        st.error(f"Error simplifying geometry: {str(e)}")
        return geom_input

# Set page config
st.set_page_config(
    page_title="GeoJSON Polygon Simplifier",
    layout="wide"
)

# App title and description
st.title("GeoJSON Polygon Simplifier")
st.write("Upload a GeoJSON file, analyze and simplify polygon vertices, then download the simplified file.")

# Sidebar for controls
with st.sidebar:
    st.header("Settings")
    max_vertices = st.number_input("Maximum Vertices per Polygon", min_value=3, max_value=1000, value=40)
    st.write("---")
    st.write("Instructions:")
    st.write("1. Upload a GeoJSON file")
    st.write("2. Adjust the maximum vertices")
    st.write("3. Click 'Simplify Polygons'")
    st.write("4. Download the simplified file")

# File uploader
uploaded_file = st.file_uploader("Choose a GeoJSON file", type=["geojson", "json"])

if uploaded_file is not None:
    # Process the uploaded file
    try:
        # Read the GeoJSON file
        gdf = gpd.read_file(uploaded_file)
        
        # Display basic information about the file
        st.subheader("File Information")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Features", len(gdf))
        with col2:
            st.metric("Geometry Type", str(gdf.geometry.iloc[0].geom_type))
        with col3:
            total_vertices = sum(gdf.geometry.apply(count_polygon_coordinates))
            st.metric("Total Vertices", total_vertices)
        
        # Show a sample of the data
        st.subheader("Data Preview")
        st.dataframe(gdf.head())
        
        # Display a map if there's geometry
        st.subheader("Map Preview")
        st.map(gdf)
        
        # Analyze vertices
        st.subheader("Vertices Analysis")
        vertex_counts = gdf.geometry.apply(count_polygon_coordinates)
        avg_vertices = vertex_counts.mean()
        max_count = vertex_counts.max()
        min_count = vertex_counts.min()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Average Vertices per Feature", f"{avg_vertices:.1f}")
        with col2:
            st.metric("Maximum Vertices", max_count)
        with col3:
            st.metric("Minimum Vertices", min_count)
        
        # Simplify the polygons
        if st.button("Simplify Polygons"):
            with st.spinner("Simplifying polygons..."):
                # Create a copy of the GeoDataFrame to avoid modifying the original
                simplified_gdf = gdf.copy()
                
                # Apply the simplification function to each geometry
                simplified_gdf['geometry'] = simplified_gdf.geometry.apply(
                    lambda geom: fix_vertices(geom, max_vertices=max_vertices)
                )
                
                # Calculate new vertex count
                new_total_vertices = sum(simplified_gdf.geometry.apply(count_polygon_coordinates))
                reduction_percentage = ((total_vertices - new_total_vertices) / total_vertices) * 100 if total_vertices > 0 else 0
                
                # Display results
                st.success(f"Simplification complete! Reduced vertices by {reduction_percentage:.1f}%")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Original Vertices", total_vertices)
                with col2:
                    st.metric("Simplified Vertices", new_total_vertices, delta=f"-{total_vertices - new_total_vertices}")
                
                # Display simplified map
                st.subheader("Simplified Map Preview")
                st.map(simplified_gdf)
                
                # Provide download option
                geojson_str = simplified_gdf.to_json()
                st.download_button(
                    label="Download Simplified GeoJSON",
                    data=geojson_str,
                    file_name="simplified_polygons.geojson",
                    mime="application/json"
                )
                
                # Show a comparison of a random feature before and after
                if len(gdf) > 0:
                    st.subheader("Sample Feature Comparison")
                    col1, col2 = st.columns(2)
                    
                    sample_idx = 0
                    with col1:
                        st.write("Original Feature")
                        original_vertices = count_polygon_coordinates(gdf.geometry.iloc[sample_idx])
                        st.write(f"Vertices: {original_vertices}")
                        st.write(gdf.iloc[[sample_idx]])
                    
                    with col2:
                        st.write("Simplified Feature")
                        simplified_vertices = count_polygon_coordinates(simplified_gdf.geometry.iloc[sample_idx])
                        st.write(f"Vertices: {simplified_vertices}")
                        st.write(simplified_gdf.iloc[[sample_idx]])
    
    except Exception as e:
        st.error(f"Error processing the file: {str(e)}")
else:
    st.info("Please upload a GeoJSON file to begin.")

# Add some additional information at the bottom
st.markdown("---")
st.markdown("This app simplifies polygon geometries using the Visvalingam-Whyatt algorithm to reduce the number of vertices while preserving the shape as much as possible.")
