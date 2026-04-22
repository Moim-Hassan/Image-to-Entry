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

# --- CONFIGURATION ---
load_dotenv(dotenv_path=Path(__file__).parent / '.env')
g_api = os.environ.get('gapi')

cl = genai.Client(api_key=g_api)

# --- IMAGE GENERATION FUNCTION ---
# def generate_product_images(product_name, brand, category, description):
#     prompt = (
#         f"Professional product photography of {brand} {product_name}, "
#         f"{category}. Clean white background, studio lighting, "
#         f"high resolution, commercial product shot. {description[:100]}"
#     )
#     try:
#         response = cl.models.generate_images(
#             model='gemini-2.5-flash-image',
#             prompt=prompt,
#             config=types.GenerateImagesConfig(
#                 number_of_images=3,
#                 aspect_ratio="1:1"
#             )
#         )
#         images = []
#         for img in response.generated_images:
#             pil_img = Image.open(io.BytesIO(img.image.image_bytes))
#             images.append(pil_img)
#         return images
#     except Exception as e:
#         st.warning(f"Image generation failed: {e}")
#         return []
st.header('Image to Entry', divider=True, text_alignment='center')

a = st.file_uploader("Upload images", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)

if a:
    st.subheader("Uploaded Images", divider=True, text_alignment='center')
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

                # # 2. AI Image Generation
                # st.session_state['generated_images'] = generate_product_images(
                #     product_name=product_data.get('product_name_en', 'product'),
                #     brand=product_data.get('brand', ''),
                #     category=product_data.get('category', ''),
                #     description=product_data.get('description', '')
                # )

            except Exception as e:
                st.error(f"Error: {e}")

    # --- DISPLAY & EDIT SECTION ---
    if 'product_data' in st.session_state:
        st.subheader("Edit Product Details", divider=True, text_alignment='center')

        edited_data = {}
        data = st.session_state['product_data']
        col1, col2 = st.columns(2)

        for idx, (key, value) in enumerate(data.items()):
            target_col = col1 if idx % 2 == 0 else col2
            if 'description' in key.lower():
                edited_data[key] = target_col.text_area(label=key, value=str(value), height=100)
            else:
                edited_data[key] = target_col.text_input(label=key, value=str(value))

        # # --- GENERATED IMAGES SECTION ---
        # st.subheader("AI Generated Product Images", divider=True)
        # gen_imgs = st.session_state.get('generated_images', [])

        # if gen_imgs:
        #     img_cols = st.columns(len(gen_imgs))
        #     for idx, pil_img in enumerate(gen_imgs):
        #         with img_cols[idx]:
        #             st.image(pil_img, use_container_width=True)
        #             if st.session_state.get('selected_img_idx') == idx:
        #                 st.success("Selected!")
        #             else:
        #                 if st.button(f"Select Image {idx+1}", key=f"img_{idx}"):
        #                     st.session_state['selected_img_idx'] = idx
        #                     st.rerun()
        # else:
        #     st.info("No images generated yet.")

        # --- DOWNLOAD SECTION ---
        st.divider()

        # Convert selected PIL image to base64 for CSV storage
        selected_idx = st.session_state.get('selected_img_idx')
        selected_b64 = ''
        if selected_idx is not None and gen_imgs:
            buf = io.BytesIO()
            gen_imgs[selected_idx].save(buf, format='PNG')
            selected_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

        edited_data['generated_image_b64'] = selected_b64

        final_df = pd.DataFrame([edited_data])
        csv = final_df.to_csv(index=False).encode('utf-8-sig')

        st.download_button(
            label="Download as CSV",
            data=csv,
            file_name=f"product_entry_{edited_data.get('brand', 'item')}.csv",
            mime='text/csv',
            type="primary"
        )
