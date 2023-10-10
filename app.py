import streamlit as st
from helpers import *
import folium
from streamlit_folium import folium_static 
from folium.plugins import TimestampedGeoJson

#---------------SETTINGS--------------------
page_title = "Geo Tenants"
page_icon = ":world-map:"  #https://www.webfx.com/tools/emoji-cheat-sheet/
layout = "centered"
initial_sidebar_state="collapsed"
#-------------------------------------------

st.set_page_config(page_title=page_title, page_icon=page_icon, layout=layout, initial_sidebar_state=initial_sidebar_state)

# --- HIDE STREAMLIT STYLE ---
hide_st_style = """
            <style>
            footer {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# ----- FUNCTIONS -----
def blank(): return st.write('') 

def password_authenticate(pwsd):

    if pwsd in st.secrets["ADMIN"]:
        return "Admin"

tenants = run_sql_query(all_tenants)
master_accounts = grab_pkl('rd-demographics', 'accounts/master_accounts.pkl')
facilities = run_sql_query(facilities_data)

list_rds = facilities['rd'].tolist()
geocoded_rds = facilities[['rd', 'latitude', 'longitude', 'acq_date']]

enter_password = st.sidebar.text_input("Password", type = 'password')

if password_authenticate(enter_password):
    st.session_state['valid_password'] = True
else: 
    st.warning("Please Enter Valid Password in the Sidebar")
    st.session_state['valid_password'] = False

st.title(page_title)

password = password_authenticate(enter_password)

if password == "Admin":
        
    with st.form("entry_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        selected_rds = col1.multiselect("Select a RD:", list_rds, key=list)
        layers = col2.selectbox('Select a Layer:', ["Current Tenants", "Time Series of Tenants", "Highlight Bad Debt Tenants"])
        
        current = True

        if layers in ["Time Series of Tenants", "Highlight Bad Debt Tenants"]:
            current = False
       
        submitted = st.form_submit_button("Submit")
    if submitted:
        if layers == "Current Tenants":
            st.info("This is showing the addresses for the current tenants of the selected facilities.", icon="ℹ")
        if layers == "Time Series of Tenants":
            st.info("This is showing the addresses for tenants over time of the selected facilities.", icon="ℹ")
        if layers == "Highlight Bad Debt Tenants":
            st.info("This is showing the addresses for all tenants over time of the selected facilities and highlighting in red the tenants who left bad debt.", icon="ℹ")
        
        with st.spinner("Searching for tenants..."):
            
            if selected_rds:  # Check if the list is not empty
                first_geocoded_rds = geocoded_rds[geocoded_rds['rd'] == selected_rds[0]]
            else:
                st.warning("No RD selected. Please select at least one RD.")
            m = folium.Map(location=[first_geocoded_rds["latitude"].iloc[0], first_geocoded_rds["longitude"].iloc[0]], zoom_start=11, tiles=None, control_scale=True)

            esri_street_map = folium.TileLayer(
                tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                attr='Esri',
                name='Esri Satellite',
                overlay=False,
                control=True
            ).add_to(m)

            esri_labels = folium.TileLayer(
                tiles='https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
                attr='Esri',
                name='Esri Labels',
                overlay=True,
                control=True
            ).add_to(m)
            
            esri_street_map.add_to(m)

            # Define tenant colors for each facility
            tenant_colors = ["#34ECF4", "#8CF434", "#9C34F4", "#F49C34", "#F4348C", "#34F43C", "#3C34F4", "#f43c34"]

            # Call the specific_rds_geocoded function for each RD and concatenate the results
            all_rd_geocoded = specific_rds_geocoded(tenants, selected_rds, current, master_accounts)

            geocoded = all_rd_geocoded[['site_code', 'account_id', 'lat', 'lon', 'bad_debt']]

            # Define bad debt color
            bad_debt_color = "#f43c34"

            for index, rd in enumerate(selected_rds):
                selected_geocoded_rds = geocoded_rds[geocoded_rds['rd'] == rd]

                # Add custom image marker for the facility
                icon = folium.CustomIcon(icon_image="rd_logo.png", icon_size=(35, 35))
                folium.Marker(
                    location=[selected_geocoded_rds["latitude"].iloc[0], selected_geocoded_rds["longitude"].iloc[0]],
                    icon=icon,
                    popup=f"{rd}",
                ).add_to(m)
                
                if layers == "Current Tenants" or layers == "Highlight Bad Debt Tenants":
                    # Filter tenant locations for the current facility
                    current_rd_geocoded = geocoded[geocoded['site_code'] == rd]

                    # Add scatter markers for tenant locations
                    for _, row in current_rd_geocoded.iterrows():
                        # Default color
                        color = tenant_colors[index % len(tenant_colors)]

                        # If layers is "Bad Debt" and bad_debt is True for this row, change the color
                        if layers == "Highlight Bad Debt Tenants" and row["bad_debt"]:
                            color = bad_debt_color

                        folium.CircleMarker(
                            location=[row["lat"], row["lon"]],
                            radius=5,
                            color=color,
                            fill=True,
                            fill_color=color,
                            fill_opacity=0.7,
                            popup=f"{row['site_code']} account {int(row['account_id'])}",
                        ).add_to(m)

                

            if layers == "Current Tenants" or layers == "Highlight Bad Debt Tenants":
                folium_static(m)
            
            if layers == "Time Series of Tenants":
                dated_dict = generate_date_dict(all_rd_geocoded, facilities)
                # Assuming selected_rds is a list of RDs
                rd_colors = {rd: tenant_colors[i % len(tenant_colors)] for i, rd in enumerate(selected_rds)}
                geojson_data = dict_to_geojson(dated_dict,rd_colors )
                
                TimestampedGeoJson(
                    geojson_data,
                    period="P1M",
                    duration="P1M",
                    transition_time=200,
                    auto_play=True,
                    loop=False,
                    loop_button=True,
                    time_slider_drag_update=True,
                    date_options="YYYY/MM/DD",
                ).add_to(m)

                folium_static(m)




