import os
import fitz  # PyMuPDF
import json

pdf_path = '23-10-EG-400-A-b_STD60_Klima_W&MPlanung_20250207.pdf'
output_base = 'extracted_output'

os.makedirs(output_base, exist_ok=True)

# --- Create Subdirectories ---
images_dir = os.path.join(output_base, "images")
texts_dir = os.path.join(output_base, "texts")
svg_pages_dir = os.path.join(output_base, "svg_pages")
drawings_dir = os.path.join(output_base, "drawings_data")
attachments_dir = os.path.join(output_base, "attachments")

os.makedirs(images_dir, exist_ok=True)
os.makedirs(texts_dir, exist_ok=True)
os.makedirs(svg_pages_dir, exist_ok=True)
os.makedirs(drawings_dir, exist_ok=True)
os.makedirs(attachments_dir, exist_ok=True)

print(f"Output directories created/ensured under: {output_base}")

try:
    # Open the PDF
    doc = fitz.open(pdf_path)
    print(f"Successfully opened PDF: {pdf_path}")
    print(f"Number of pages: {len(doc)}")

    # --- 1. Extract Raster Images ---
    print("\n--- Starting Raster Image Extraction ---")
    image_count = 0
    for page_index in range(len(doc)):
        page = doc[page_index]
        image_list = page.get_images(full=True)
        if not image_list:
            continue

        print(f"Found {len(image_list)} image(s) on page {page_index + 1}")
        for img_index, img in enumerate(image_list):
            xref = img[0]
            try:
                image_info = doc.extract_image(xref)
                if not image_info:
                    print(f"  - Could not extract image info for xref {xref} on page {page_index + 1}")
                    continue

                image_bytes = image_info["image"]
                image_ext = image_info["ext"]

                image_filename = f"page{page_index+1}_img{xref}.{image_ext}"
                image_filepath = os.path.join(images_dir, image_filename)

                # Save the image file
                with open(image_filepath, "wb") as img_file:
                    img_file.write(image_bytes)
                print(f"  - Saved: {image_filepath}")
                image_count += 1
            except Exception as e:
                print(f"  - Error extracting image xref {xref} on page {page_index + 1}: {e}")
    if image_count == 0:
         print("No raster images found or extracted.")
    else:
        print(f"--- Finished Raster Image Extraction ({image_count} images saved) ---")


    # --- 2. Extract Text from Each Page ---
    print("\n--- Starting Text Extraction ---")
    for page_index in range(len(doc)):
        page = doc[page_index]
        try:
            text = page.get_text()
            if text.strip():
                text_filename = f"page_{page_index+1}.txt"
                text_filepath = os.path.join(texts_dir, text_filename)

                with open(text_filepath, "w", encoding="utf-8") as text_file:
                    text_file.write(text)
                print(f"Extracted text from page {page_index+1} saved to: {text_filepath}")
            else:
                print(f"No text found on page {page_index+1}")
        except Exception as e:
            print(f"Error extracting text from page {page_index + 1}: {e}")
    print("--- Finished Text Extraction ---")


    # --- 3. Extract Each Page as SVG ---
    # This often captures vector graphics like DWG/SVG embedded in the page stream
    print("\n--- Starting Page SVG Export ---")
    svg_count = 0
    for page_index in range(len(doc)):
        page = doc[page_index]
        try:
            svg_data = page.get_svg_image(text_as_path=False)

            svg_filename = f"page_{page_index+1}.svg"
            svg_filepath = os.path.join(svg_pages_dir, svg_filename)

            with open(svg_filepath, "w", encoding="utf-8") as svg_file:
                svg_file.write(svg_data)
            print(f"Exported page {page_index+1} as SVG to: {svg_filepath}")
            svg_count += 1
        except Exception as e:
            print(f"Error exporting page {page_index + 1} as SVG: {e}")
    if svg_count > 0:
        print(f"--- Finished Page SVG Export ({svg_count} SVGs saved) ---")
    else:
        print("--- No pages exported as SVG (check for errors above) ---")


    # --- 4. Extract Embedded Files / Attachments (Standard Method) ---
    print("\n--- Checking for Standard Embedded Files (Attachments) ---")
    try:
        att_count = doc.embfile_count()
        if att_count > 0:
            print(f"Found {att_count} embedded file(s).")
            for i in range(att_count):
                try:
                    info = doc.embfile_info(i)
                    file_name = info["filename"]
                    print(f"  - Extracting attachment: {file_name}")

                    output_folder = attachments_dir

                    extracted_data = doc.embfile_get(i)
                    file_bytes = extracted_data.get('buffer') or extracted_data.get('file')

                    if file_bytes:
                        file_path = os.path.join(output_folder, file_name)
                        with open(file_path, "wb") as att_file:
                            att_file.write(file_bytes)
                        print(f"    Saved attachment to: {file_path}")
                    else:
                        print(f"    Could not retrieve data for attachment: {file_name}")
                except Exception as e:
                    print(f"    Error processing attachment index {i} ({info.get('filename', 'N/A')}): {e}")
        else:
            print("No standard embedded attachments found.")
        print("--- Finished Checking Attachments ---")
    except Exception as e:
        print(f"Error during attachment check/extraction: {e}")


    # --- [Optional] 5. Extract Raw Drawing Commands ---
    # This extracts vector drawing commands (lines, curves, rects) as structured data.
    # Useful for analysis but might not directly give you usable SVG/DWG files.
    print("\n--- Starting Raw Drawing Extraction (Optional) ---")
    drawing_count = 0
    for page_index in range(len(doc)):
        page = doc[page_index]
        try:
            drawings = page.get_drawings()
            if drawings:
                drawing_filename = f"page_{page_index+1}_drawings.json"
                drawing_filepath = os.path.join(drawings_dir, drawing_filename)

                with open(drawing_filepath, "w", encoding="utf-8") as json_file:
                    json.dump(drawings, json_file, indent=2)
                print(f"Extracted drawing data for page {page_index+1} saved to: {drawing_filepath}")
                drawing_count += 1
            else:
                print(f"No raw drawing commands found on page {page_index+1}")
        except Exception as e:
            print(f"Error extracting drawings from page {page_index + 1}: {e}")
    if drawing_count > 0:
        print(f"--- Finished Raw Drawing Extraction ({drawing_count} files saved) ---")
    else:
        print("--- No raw drawings extracted ---")

except FileNotFoundError:
    print(f"Error: PDF file not found at '{pdf_path}'")
except fitz.fitz.FileNotFoundError:
     print(f"Error: PyMuPDF could not open the file '{pdf_path}'. It might be corrupted or not a PDF.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
finally:
    if 'doc' in locals() and doc:
        doc.close()
        print("\nPDF document closed.")

print("\nExtraction process finished.")
