import streamlit as st
from google import genai
from google.genai import types
import os, io, base64
from dotenv import load_dotenv
from PIL import Image
import pandas as pd
import json, re
from pathlib import Path
from google.genai import types
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURATION ---
load_dotenv(dotenv_path=Path(__file__).parent / '.env')
g_api = os.environ.get('gapi')

cl = genai.Client(api_key=g_api)
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- GOOGLE SHEETS SETUP ---
def add_to_google_sheet(data_dict):
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        creds_json_str = os.environ.get('G_SHEET_CREDS')
        # ... (your cleaning logic) ...
        
        creds_info = json.loads(creds_json_str)
        
        # Use the modern Credentials class here:
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        client = gspread.authorize(creds)
        
        sheet = client.open_by_key("1t9kAYh_RalMG4tdQuPtLPZoiVpk3zIrJmX4IAKy8g7I").sheet1 
        sheet.append_row(list(data_dict.values()))
        return True
    except Exception as e:
        st.error(f"Google Sheet Error: {e}")
        return False

st.header('Image to Entry', divider=True)

a = st.file_uploader("Upload images", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)

if a:
    st.subheader("Uploaded Images", divider=True)
    col = st.columns(len(a))
    pimg = []
    for i, file in enumerate(a):
        img_bytes = file.getvalue()
        with col[i]:
            st.image(img_bytes)
        x = Image.open(io.BytesIO(img_bytes))
        if x.mode in ("RGBA", "P"): x = x.convert("RGB")
        x.thumbnail((768, 768), Image.Resampling.LANCZOS)
        pimg.append(x)

    prompt = """Extract details for the provided product images. Return ONLY a valid JSON object with the following exact keys (all values must be strings):
    - "product_name_en": Product name in English
    - "product_name_bn": Product name in Bangla
    - "category": Product category (match from rokomari.com category)
    - "brand": Brand name
    - "sub_title_en": Sub-title in English
    - "sub_title_bn": Sub-title in Bangla
    - "height_ft": Height in feet (if available else approximate)
    - "length_ft": Length in feet (if available else approximate)
    - "width_ft": Width in feet (if available else approximate)
    - "warranty_type": Warranty Type
    - "warranty_time": Warranty Time (if available)
    - "material": Material / Specifications
    - "description_en": A detailed description in 150 words.
    - "description_bn": A detailed description in 150 words.
    - "mrp": MRP (if available)
    - "sell_price": Sell price (if available)
    
    Output raw JSON only without any markdown formatting. No ecommerce names/links. Blank if not found"""

    if st.button('Generate', type='primary'):
        with st.spinner('AI is extracting details for the images...'):
            try:
                # 1. AI Text Generation
                res = cl.models.generate_content(
                    model='gemini-3.1-flash-lite-preview',
                    contents=[prompt, *pimg]
                )
                raw_json = res.text
                match = re.search(r'\{.*\}', raw_json, re.DOTALL)
                if match:
                    raw_json = match.group(0)
                product_data = json.loads(raw_json)
                st.session_state['product_data'] = product_data


            except Exception as e:
                st.error(f"Error: {e}")

    # --- DISPLAY & EDIT SECTION ---
if 'product_data' in st.session_state:
    st.subheader("Edit Product Details", divider=True)

    edited_data = {}
    data = st.session_state['product_data']
    col1, col2 = st.columns(2)

    for idx, (key, value) in enumerate(data.items()):
        target_col = col1 if idx % 2 == 0 else col2
        if 'description' in key.lower():
            edited_data[key] = target_col.text_area(label=key, value=str(value), height=100)
        else:
            edited_data[key] = target_col.text_input(label=key, value=str(value))

    st.divider()
    final_df = pd.DataFrame([edited_data])
    if st.button("🚀 Submit", type="primary", use_container_width=True):
        with st.spinner("Pushing to Google Sheets..."):
            if add_to_google_sheet(edited_data):
                st.toast("Success! Row added.", icon="✅")
                # st.snow()
