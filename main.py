import os
import fitz  # PyMuPDF
import io
from PIL import Image

# Specify your PDF file and a base output directory
pdf_path = '23-10-EG-400-A-b_STD60_Klima_W&MPlanung_20250207.pdf'
output_base = 'extracted_output'
os.makedirs(output_base, exist_ok=True)

# Create subdirectories for images, texts, and attachments
images_dir = os.path.join(output_base, "images")
texts_dir = os.path.join(output_base, "texts")
attachments_dir = os.path.join(output_base, "attachments")
os.makedirs(images_dir, exist_ok=True)
os.makedirs(texts_dir, exist_ok=True)
os.makedirs(attachments_dir, exist_ok=True)

# Open the PDF
doc = fitz.open(pdf_path)

### 1. Extract Images
for page_index in range(len(doc)):
    page = doc[page_index]
    image_list = page.get_images(full=True)
    if not image_list:
        continue

    for img in image_list:
        xref = img[0]
        image_info = doc.extract_image(xref)
        image_bytes = image_info["image"]
        image_ext = image_info["ext"]

        image_type_dir = os.path.join(images_dir, image_ext)
        os.makedirs(image_type_dir, exist_ok=True)
        
        image_filename = f"page{page_index+1}_img{xref}.{image_ext}"
        image_filepath = os.path.join(image_type_dir, image_filename)

        # Save the image file
        with open(image_filepath, "wb") as img_file:
            img_file.write(image_bytes)
        print(f"Extracted image saved at: {image_filepath}")

### 2. Extract Text from Each Page
for page_index in range(len(doc)):
    page = doc[page_index]
    text = page.get_text()
    text_filename = f"page_{page_index+1}.txt"
    text_filepath = os.path.join(texts_dir, text_filename)
    
    with open(text_filepath, "w", encoding="utf-8") as text_file:
        text_file.write(text)
    print(f"Extracted text from page {page_index+1} saved at: {text_filepath}")

### 3. Extract Embedded Files / Attachments
att_count = doc.embfile_count
if att_count() > 0:
    for i in range(att_count):
        info = doc.embfile_info(i)
        file_name = info["filename"]
        
        extracted = doc.embfile_get(i)
        file_data = extracted["file"]

        file_path = os.path.join(attachments_dir, file_name)
        with open(file_path, "wb") as att_file:
            att_file.write(file_data)
        print(f"Extracted attachment saved at: {file_path}")
else:
    print("No embedded attachments found.")


doc.close()
