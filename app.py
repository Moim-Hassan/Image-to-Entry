import streamlit as st
from google import genai
import os, io
from dotenv import load_dotenv
from PIL import Image
import pandas as pd
import json

load_dotenv()
api=os.environ.get('gapi')

cl=genai.Client(api_key=api)

st.header('Image to Entry',divider=True,text_alignment='center',width='stretch')


a=st.file_uploader("Upload images",type=['jpg','jpeg','png'],
                       accept_multiple_files=True)
st.image(a)
if a:
    pimg=[]
    for i in a:
        x=Image.open(i)
        x.thumbnail((768, 768), Image.Resampling.LANCZOS) 
        pimg.append(x)
    prompt = """Generate product name, category, material and other specifications which are available
      for these photos. Generate product info in raw JSON format. Do not include markdown code blocks.
        Note that other spacification key should be like brand, not specification.brand"""
    
    if st.button('Generate',type='primary'):
        with st.spinner('AI is generating the image details'):

            res = cl.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[prompt,*pimg]
       )
            # st.markdown(res.text)
            st.subheader("ALL The data Show Below",divider=True,text_alignment='center')
            df=json.loads(res.text)
            df=pd.json_normalize(df)
            st.write(df.T.reset_index())
