import streamlit as st
import geopandas as gpd
from shapely.geometry import shape, mapping, Polygon, MultiPolygon
from shapely import wkt
import visvalingamwyatt as vw
import pandas as pd

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

    except Exception:
        return geom_input

# Set up the app
st.title("GeoJSON Polygon Simplifier")

# Simple settings
max_vertices = st.slider("Maximum Vertices per Polygon", min_value=3, max_value=100, value=40)

# File uploader
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
            
            # Basic information
            total_features = len(combined_gdf)
            total_vertices = sum(combined_gdf.geometry.apply(count_polygon_coordinates))
            
            st.write(f"**Total Features:** {total_features}")
            st.write(f"**Total Vertices:** {total_vertices}")
            
            # Simplify button
            if st.button("Simplify Polygons"):
                with st.spinner("Simplifying polygons..."):
                    # Create a copy of the GeoDataFrame
                    simplified_gdf = combined_gdf.copy()
                    
                    # Apply the simplification function to each geometry
                    simplified_gdf['geometry'] = simplified_gdf.geometry.apply(
                        lambda geom: fix_vertices(geom, max_vertices=max_vertices)
                    )
                    
                    # Calculate new vertex count
                    new_total_vertices = sum(simplified_gdf.geometry.apply(count_polygon_coordinates))
                    reduction = total_vertices - new_total_vertices
                    reduction_percentage = (reduction / total_vertices * 100) if total_vertices > 0 else 0
                    
                    # Display results
                    st.success(f"Simplification complete!")
                    st.write(f"**Original Vertices:** {total_vertices}")
                    st.write(f"**Simplified Vertices:** {new_total_vertices}")
                    st.write(f"**Vertices Reduced:** {reduction} ({reduction_percentage:.1f}%)")
                    
                    # Provide download option for combined file
                    geojson_str = simplified_gdf.to_json()
                    st.download_button(
                        label="Download Simplified GeoJSON",
                        data=geojson_str,
                        file_name="simplified.geojson",
                        mime="application/json"
                    )
    
    except Exception as e:
        st.error(f"Error processing files: {str(e)}")
else:
    st.info("Please upload GeoJSON files to begin.")
