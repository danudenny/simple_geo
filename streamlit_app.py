import streamlit as st
import geopandas as gpd
import json
from shapely.geometry import shape, mapping, Polygon, MultiPolygon
from shapely import wkt
import visvalingamwhyatt as vw
import pandas as pd
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
    page_title="Multiple GeoJSON Polygon Simplifier",
    layout="wide"
)

# App title and description
st.title("Multiple GeoJSON Polygon Simplifier")
st.write("Upload multiple GeoJSON files, combine them, analyze and simplify polygon vertices, then download the simplified file.")

# Sidebar for controls
with st.sidebar:
    st.header("Settings")
    max_vertices = st.number_input("Maximum Vertices per Polygon", min_value=3, max_value=1000, value=40)
    st.write("---")
    st.write("Instructions:")
    st.write("1. Upload one or more GeoJSON files")
    st.write("2. Adjust the maximum vertices")
    st.write("3. Click 'Simplify Polygons'")
    st.write("4. Download the simplified file")

# File uploader for multiple files
uploaded_files = st.file_uploader("Choose GeoJSON files", type=["geojson", "json"], accept_multiple_files=True)

if uploaded_files:
    try:
        # Process the uploaded files
        with st.spinner("Processing uploaded files..."):
            # Read each file and combine them
            gdfs = []
            for uploaded_file in uploaded_files:
                file_gdf = gpd.read_file(uploaded_file)
                file_gdf['source_file'] = uploaded_file.name
                gdfs.append(file_gdf)
            
            # Combine all GeoDataFrames
            combined_gdf = pd.concat(gdfs, ignore_index=True)
            
            # Display basic information about the combined file
            st.subheader("Combined Files Information")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Files Merged", len(uploaded_files))
            with col2:
                st.metric("Total Features", len(combined_gdf))
            with col3:
                geom_types = combined_gdf.geometry.geom_type.unique().tolist()
                st.metric("Geometry Types", ", ".join(geom_types))
            with col4:
                total_vertices = sum(combined_gdf.geometry.apply(count_polygon_coordinates))
                st.metric("Total Vertices", total_vertices)
            
            # Show a sample of the data
            st.subheader("Data Preview")
            st.dataframe(combined_gdf.head())
            
            # Analyze vertices
            st.subheader("Vertices Analysis")
            vertex_counts = combined_gdf.geometry.apply(count_polygon_coordinates)
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
            
            # Display histogram of vertex counts
            st.subheader("Vertex Count Distribution")
            hist_data = pd.DataFrame({"Vertices per Feature": vertex_counts})
            st.bar_chart(hist_data["Vertices per Feature"].value_counts().sort_index())
            
            # Display file breakdown
            st.subheader("File Breakdown")
            file_stats = combined_gdf.groupby('source_file').agg(
                Features=('geometry', 'count'),
                Total_Vertices=('geometry', lambda x: sum(x.apply(count_polygon_coordinates))),
                Avg_Vertices=('geometry', lambda x: x.apply(count_polygon_coordinates).mean())
            )
            st.dataframe(file_stats)
            
            # Simplify the polygons
            if st.button("Simplify Polygons"):
                with st.spinner("Simplifying polygons..."):
                    # Create a copy of the GeoDataFrame to avoid modifying the original
                    simplified_gdf = combined_gdf.copy()
                    
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
                    
                    # Show file breakdown after simplification
                    st.subheader("File Breakdown After Simplification")
                    simplified_file_stats = simplified_gdf.groupby('source_file').agg(
                        Features=('geometry', 'count'),
                        Total_Vertices=('geometry', lambda x: sum(x.apply(count_polygon_coordinates))),
                        Avg_Vertices=('geometry', lambda x: x.apply(count_polygon_coordinates).mean())
                    )
                    
                    # Add comparison columns
                    comparison_stats = pd.merge(
                        file_stats, 
                        simplified_file_stats, 
                        on='source_file', 
                        suffixes=('_original', '_simplified')
                    )
                    comparison_stats['Vertices_Reduced'] = comparison_stats['Total_Vertices_original'] - comparison_stats['Total_Vertices_simplified']
                    comparison_stats['Reduction_Percentage'] = (comparison_stats['Vertices_Reduced'] / comparison_stats['Total_Vertices_original'] * 100).round(1)
                    
                    st.dataframe(comparison_stats)
                    
                    # Show a comparison of vertex counts before and after for top features
                    st.subheader("Top Features by Vertex Count Reduction")
                    
                    # Create comparison dataframe
                    compare_df = pd.DataFrame({
                        'Source File': combined_gdf['source_file'],
                        'Original Vertices': vertex_counts,
                        'Simplified Vertices': simplified_gdf.geometry.apply(count_polygon_coordinates)
                    })
                    compare_df['Reduction'] = compare_df['Original Vertices'] - compare_df['Simplified Vertices']
                    compare_df['Reduction %'] = (compare_df['Reduction'] / compare_df['Original Vertices'] * 100).round(1)
                    
                    # Show the comparison
                    st.dataframe(compare_df.sort_values('Reduction', ascending=False).head(10))
                    
                    # Provide download options
                    st.subheader("Download Options")
                    
                    # Download combined simplified file
                    geojson_str = simplified_gdf.to_json()
                    st.download_button(
                        label="Download Combined Simplified GeoJSON",
                        data=geojson_str,
                        file_name="combined_simplified.geojson",
                        mime="application/json"
                    )
                    
                    # Option to download individual simplified files
                    st.write("Download Individual Simplified Files:")
                    
                    # Create columns for download buttons
                    cols = st.columns(min(4, len(uploaded_files)))
                    
                    # Create download buttons for each file
                    for i, file_name in enumerate(simplified_gdf['source_file'].unique()):
                        file_gdf = simplified_gdf[simplified_gdf['source_file'] == file_name]
                        file_json = file_gdf.to_json()
                        
                        col_idx = i % 4
                        with cols[col_idx]:
                            st.download_button(
                                label=f"Download {file_name}",
                                data=file_json,
                                file_name=f"simplified_{file_name}",
                                mime="application/json",
                                key=f"download_{i}"
                            )
    
    except Exception as e:
        st.error(f"Error processing the files")
        st.exception(e)
else:
    st.info("Please upload GeoJSON files to begin.")

# Add some additional information at the bottom
st.markdown("---")
st.markdown("This app simplifies polygon geometries using the Visvalingam-Whyatt algorithm to reduce the number of vertices while preserving the shape as much as possible.")
