import pandas as pd
import boto3
import streamlit as st
import pickle 
from sql_queries import *
from datetime import datetime
from dateutil.relativedelta import relativedelta

MASTER_ACCESS_KEY = st.secrets['MASTER_ACCESS_KEY']
MASTER_SECRET = st.secrets['MASTER_SECRET']

st.cache_data(ttl=60*60*24)
def grab_pkl(bucket, key):
    s3 = boto3.client('s3', region_name='us-west-1',
                aws_access_key_id=MASTER_ACCESS_KEY,
                aws_secret_access_key=MASTER_SECRET)

    master_accounts_cache = pickle.loads(s3.get_object(Bucket=bucket, Key=key)['Body'].read())

    return master_accounts_cache

## Grabbing all accounts from a list of RDs
def specific_rds_geocoded(tenants, rds, current, master_accounts):
    rd_tenants = tenants[tenants['site_code'].isin(rds)]
    if current:
        rd_tenants = rd_tenants[rd_tenants['moved_out'] == False]

    # convert rd_tenants['id'] to set for faster membership checking
    account_ids = set(rd_tenants['id'].values)

    data_list = []
    for account_id in account_ids:
        account_data = master_accounts.get(account_id)
        if account_data is not None:
            data = {
                "account_id": account_id,
                "lat": account_data["location"]["location"]["lat"],
                "lon": account_data["location"]["location"]["lng"],
                "full_fips": account_data["census"]["full_fips"],
                "site_code": rd_tenants.loc[rd_tenants['id'] == account_id, 'site_code'].values[0],
                "move_in_date": rd_tenants.loc[rd_tenants['id'] == account_id, 'move_in_date'].values[0],
                "moved_out_at": rd_tenants.loc[rd_tenants['id'] == account_id, 'moved_out_at'].values[0],
                "bad_debt": rd_tenants.loc[rd_tenants['id'] == account_id, 'bad_debt'].values[0],
                "write_offs": rd_tenants.loc[rd_tenants['id'] == account_id, 'write_offs'].values[0]
            }
            data_list.append(data)

    # Convert the list of dictionaries to a DataFrame
    final_df = pd.DataFrame(data_list)

    # Select the required columns
    final_df = final_df[['site_code', 'account_id', 'move_in_date', 'moved_out_at', 'lat', 'lon', 'full_fips', 'bad_debt', 'write_offs']]

    return final_df

def generate_date_dict(df, facilities):
    data_dict = {}
    min_acq_date = facilities[facilities['rd'].isin(df['site_code'])]['acq_date'].min()
    start_date = max(pd.Timestamp('2019-05-31'), pd.Timestamp(min_acq_date))
    end_date = pd.Timestamp.today().replace(day=1) + relativedelta(months=1) - relativedelta(days=1)  # Last day of current month
    date_range = pd.date_range(start=start_date, end=end_date, freq='M')

    for _, row in df.iterrows():
        account_id = row['account_id']
        acq_date = facilities.loc[facilities['rd'] == row['site_code'], 'acq_date'].values[0]
        move_in_date = max(row['move_in_date'], acq_date)
        moved_out_at = row['moved_out_at'] if pd.notnull(row['moved_out_at']) else (end_date + relativedelta(days=1))

        if account_id not in data_dict:
            data_dict[account_id] = {
                "site_code": row["site_code"],
                "lat": row["lat"],
                "lon": row["lon"],
                "full_fips": row["full_fips"],
                "dates": []
            }

        for date in date_range:
            if pd.Timestamp(move_in_date) <= pd.Timestamp(date) < pd.Timestamp(moved_out_at):
                data_dict[account_id]["dates"].append(date)

    return data_dict


def dict_to_geojson(data_dict, rd_colors):
    features = []
    for account_id, account_data in data_dict.items():
        for date in account_data["dates"]:
            dt = datetime.combine(date, datetime.min.time())  # Convert date to datetime
            timestamp_ms = int(dt.timestamp() * 1000)  # Convert the datetime to timestamp in milliseconds
            color = rd_colors[account_data["site_code"]]  # Get the color for the RD
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [account_data["lon"], account_data["lat"]],
                },
                "properties": {
                    "site_code": account_data["site_code"],
                    "account_id": int(account_id),
                    "timestamp": date.strftime("%Y-%m-%d"),
                    "times": [timestamp_ms],  # Add times property as a list containing the timestamp in milliseconds
                    "icon": "circle",
                    "iconstyle": {
                        "color": color,
                        "fillColor": color,
                        "fillOpacity": 0.7,
                        "stroke": "false",
                        "radius": 5
                    },
                    "popup": f"{account_data['site_code']} account {int(account_id)}",  # Add popup property
                },
            }
            features.append(feature)

    geojson = {"type": "FeatureCollection", "features": features}
    return geojson


