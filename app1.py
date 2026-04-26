import streamlit as st
from google import genai
from google.genai import types
import os, io, json, re
from dotenv import load_dotenv
from PIL import Image
import pandas as pd
from pathlib import Path
import gspread
from google.oauth2.service_account import Credentials

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="Product Entry AI", page_icon="📦")

# --- 2. LOAD CREDENTIALS ---
load_dotenv(dotenv_path=Path(__file__).parent / '.env')
g_api = os.environ.get('gapi')
cl = genai.Client(api_key=g_api)

def add_to_google_sheet(data_dict):
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_json_str = os.environ.get('G_SHEET_CREDS').strip()
        if creds_json_str.startswith("'") and creds_json_str.endswith("'"):
            creds_json_str = creds_json_str[1:-1]
        creds_info = json.loads(creds_json_str)
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key("1t9kAYh_RalMG4tdQuPtLPZoiVpk3zIrJmX4IAKy8g7I").sheet1 
        sheet.append_row(list(data_dict.values()))
        return True
    except Exception as e:
        st.error(f"Google Sheet Error: {e}")
        return False

# --- 3. UPLOADER SECTION ---
st.header('📦 Image to Entry', divider='rainbow',text_alignment='center')

if 'success_msg' in st.session_state:
    st.success(st.session_state['success_msg'])
    del st.session_state['success_msg']

a = st.file_uploader("Upload product images", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True, key="my_files")

if a:
    pimg = []
    cols = st.columns(4)
    for i, file in enumerate(a):
        img_bytes = file.getvalue()
        with cols[i % 4]:
            st.image(img_bytes, use_container_width=True)
        x = Image.open(io.BytesIO(img_bytes))
        if x.mode in ("RGBA", "P"): x = x.convert("RGB")
        x.thumbnail((800, 800))
        pimg.append(x)

    prompt = """Extract details for the provided product images. Return ONLY a valid JSON object with the following exact keys (all values must be strings):
    - "product_name_en": Product name in English
    - "product_name_bn": Product name in Bangla
    - "category": Product category (match from rokomari.com category)
    - "brand": Brand name (If not found, keep blank")
    - "sub_title_en": Sub-title in English
    - "sub_title_bn": Sub-title in Bangla
    - "height_feet": Height in feet (if available else approximate)
    - "length_feet": Length in feet (if available else approximate)
    - "width_feet": Width in feet (if available else approximate)
    - "warranty_type": Warranty Type
    - "warranty_time": Warranty Time (if available)
    - "material": Material
    - "description_en": A detailed description in 150 words.
    - "description_bn": A detailed description in 150 words.
    - "mrp (৳)": MRP (if available, in bdt)
    - "sell_price (৳)": Sell price (keep it always blank, in bdt)
    
    Output raw JSON only without any markdown formatting. No ecommerce names/links. Blank if not found"""

    if st.button('✨ Generate Product Data', type='primary', use_container_width=True):
        with st.spinner('AI analyzing...'):
            try:
                res = cl.models.generate_content(model='gemini-3.1-flash-lite-preview', contents=[prompt, *pimg])
                match = re.search(r'\{.*\}', res.text, re.DOTALL)
                if match:
                    st.session_state['product_data'] = json.loads(match.group(0))
            except Exception as e:
                st.error(f"AI Error: {e}")

# --- 4. SINGLE COLUMN EDIT & SUBMIT ---
if 'product_data' in st.session_state:
    st.subheader("📝 Review & Edit Details", divider=True,text_alignment='center')

    edited_data = {}
    data = st.session_state['product_data']
    
    for key, value in data.items():
        label = key.replace('_', ' ').title()
        
        if key == "warranty_type":
            options = ["BRAND_WARRANTY", "SUPPLIER_WARRANTY", "NO_WARRANTY"]
            current_val = str(value).upper().replace(" ", "_")
            default_index = 2
            if current_val in options:
                default_index = options.index(current_val)
            edited_data[key] = st.selectbox(label, options=options, index=default_index)
            
        elif 'description' in key.lower():
            edited_data[key] = st.text_area(label, value=str(value), height=150)
            
        else:
            edited_data[key] = st.text_input(label, value=str(value))

    st.divider()
    msg_area = st.empty()

    if st.button("🚀 Submitting to Rokomari Database", type="primary", use_container_width=True):
        # FIX: Using the correct keys with (৳) symbol as defined in your prompt
        mrp_val = str(edited_data.get('mrp (৳)', '')).strip()
        sell_val = str(edited_data.get('sell_price (৳)', '')).strip()
        
        # VALIDATION LOGIC FIX:
        # We want to trigger error if:
        # 1. Field is empty
        # 2. Field says "None"
        # 3. Field contains NON-numeric characters (not isdecimal)
        if not mrp_val or not sell_val or mrp_val.lower() == "none" or not mrp_val.replace('.','',1).isdigit() or not sell_val.replace('.','',1).isdigit() or float(mrp_val)<=float(sell_val):
            msg_area.error("🚨 Please enter a valid numeric MRP and Selling Price!")
        else:
            with st.spinner("Writing to database..."):
                if add_to_google_sheet(edited_data):
                    st.session_state['success_msg'] = "🎉 Successfully submitted to Rokomari database!"
                    del st.session_state['product_data']
                    if 'my_files' in st.session_state:
                        del st.session_state["my_files"]
            st.rerun()
