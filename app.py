import streamlit as st
from google import genai
import os, io, requests, re
from dotenv import load_dotenv
from PIL import Image
import pandas as pd
import json
from pathlib import Path

# --- CONFIGURATION ---
load_dotenv(dotenv_path=Path(__file__).parent / '.env')
g_api = os.environ.get('gapi')
s_api = os.environ.get('search_api_key')
s_cx = os.environ.get('search_cx')

cl = genai.Client(api_key=g_api)

# --- WEB SEARCH FUNCTION ---
def get_web_images(query):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        'q': query,
        'key': s_api,
        'cx': s_cx,
        'searchType': 'image',
        'num': 3,
        'imgSize': 'large'
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        items = response.json().get('items', [])
        return [item['link'] for item in items]
    except Exception as e:
        return []

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
    - "category": Product category
    - "brand": Brand name
    - "sub_title_en": Sub-title in English
    - "sub_title_bn": Sub-title in Bangla
    - "height_ft": Height in feet (if available else approximate)
    - "length_ft": Length in feet (if available else approximate)
    - "width_ft": Width in feet (if available else approximate)
    - "warranty_type": Warranty Type
    - "warranty_time": Warranty Time (if available)
    - "material": Material / Specifications
    - "description": A detailed description in 100 words.
    - "mrp": MRP (if available)
    - "sell_price": Sell price (if available)
    
    Output raw JSON only without any markdown formatting. No ecommerce names/links. Blank if not found"""

    if st.button('Generate', type='primary'):
        with st.spinner('AI is generating and searching web...'):
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
                
                # 2. Web Image Search (using generated product name)
                search_q = f"{product_data.get('brand', '')} {product_data.get('product_name_en', 'product')} official photo".strip()
                st.session_state['web_images'] = get_web_images(search_q)

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

        # --- WEB IMAGES SECTION ---
        st.subheader("Suggested Web Images", divider=True)
        web_imgs = st.session_state.get('web_images', [])
        
        if web_imgs:
            img_cols = st.columns(3)
            for idx, link in enumerate(web_imgs):
                with img_cols[idx]:
                    st.image(link, use_container_width=True)
                    if st.session_state.get('selected_url') == link:
                        st.success("Selected!")
                    else:
                        if st.button(f"Select Image {idx+1}", key=f"img_{idx}"):
                            st.session_state['selected_url'] = link
                            st.rerun()
        else:
            st.info("No web images found. Check your Search API/CX settings.")

        # --- DOWNLOAD SECTION ---
        st.divider()
        # Add the selected image URL to the final data
        edited_data['web_image_url'] = st.session_state.get('selected_url', '')
        
        final_df = pd.DataFrame([edited_data])
        csv = final_df.to_csv(index=False).encode('utf-8-sig')

        st.download_button(
            label="Download as CSV",
            data=csv,
            file_name=f"product_entry_{edited_data.get('brand', 'item')}.csv",
            mime='text/csv',
            type="primary"
        )
