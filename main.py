import os
import fitz  # PyMuPDF
import json
from xml.etree import ElementTree as ET

# Input PDF and output directory
pdf_path = '23-10-EG-400-A-b_STD60_Klima_W&MPlanung_20250207.pdf'
output_base = 'extracted_output'

# Create base output folder and subdirectories
os.makedirs(output_base, exist_ok=True)

images_dir      = os.path.join(output_base, "images")
texts_dir       = os.path.join(output_base, "texts")
svg_pages_dir   = os.path.join(output_base, "svg_pages")
drawings_dir    = os.path.join(output_base, "drawings_data")
attachments_dir = os.path.join(output_base, "attachments")
vector_svgs_dir = os.path.join(output_base, "vector_svgs")
for d in [images_dir, texts_dir, svg_pages_dir, drawings_dir, attachments_dir, vector_svgs_dir]:
    os.makedirs(d, exist_ok=True)

print(f"Output directories created under: {output_base}")

try:
    # Open the PDF
    doc = fitz.open(pdf_path)
    print(f"Successfully opened PDF: {pdf_path} ({len(doc)} pages)")

    # --- 1. Extract Raster Images ---
    print("\n--- Starting Raster Image Extraction ---")
    image_count = 0
    for page_index in range(len(doc)):
        page = doc[page_index]
        for img in page.get_images(full=True):
            xref = img[0]
            try:
                info = doc.extract_image(xref)
                if not info:
                    continue
                img_bytes = info['image']
                ext = info['ext']
                fname = f"page{page_index+1}_img{xref}.{ext}"
                fpath = os.path.join(images_dir, fname)
                with open(fpath, 'wb') as f:
                    f.write(img_bytes)
                print(f"Saved raster image: {fpath}")
                image_count += 1
            except Exception as e:
                print(f"Error extracting image xref {xref} on page {page_index+1}: {e}")
    print(f"--- Raster images extracted: {image_count} ---")

    # --- 2. Extract Text from Each Page ---
    print("\n--- Starting Text Extraction ---")
    for page_index in range(len(doc)):
        page = doc[page_index]
        try:
            text = page.get_text()
            if text.strip():
                fname = f"page_{page_index+1}.txt"
                fpath = os.path.join(texts_dir, fname)
                with open(fpath, 'w', encoding='utf-8') as f:
                    f.write(text)
                print(f"Page {page_index+1} text saved: {fpath}")
        except Exception as e:
            print(f"Error extracting text on page {page_index+1}: {e}")
    print("--- Text extraction complete ---")

    # --- 3. Extract Each Page as SVG ---
    print("\n--- Starting Page SVG Export ---")
    svg_count = 0
    for page_index in range(len(doc)):
        page = doc[page_index]
        try:
            svg_data = page.get_svg_image(text_as_path=True)
            fname = f"page_{page_index+1}.svg"
            fpath = os.path.join(svg_pages_dir, fname)
            with open(fpath, 'w', encoding='utf-8') as svg_file:
                svg_file.write(svg_data)
            print(f"Exported page {page_index+1} as SVG to: {fpath}")
            svg_count += 1
        except Exception as e:
            print(f"Error exporting page {page_index+1} as SVG: {e}")
    print(f"--- Finished Page SVG Export ({svg_count} SVGs saved) ---")

    # --- 4. Extract Embedded Files / Attachments ---
    print("\n--- Starting Attachment Extraction ---")
    try:
        att_count = doc.embfile_count()
        print(f"Found {att_count} embedded file(s).")
        for i in range(att_count):
            info = doc.embfile_info(i)
            name = info.get('filename') or f'emb_{i}'
            data = doc.embfile_get(i)
            buf = data.get('buffer') or data.get('file')
            if buf:
                fpath = os.path.join(attachments_dir, name)
                with open(fpath, 'wb') as f:
                    f.write(buf)
                print(f"Saved attachment: {fpath}")
    except Exception as e:
        print(f"Error extracting attachments: {e}")
    print("--- Attachment extraction complete ---")

    # --- 5. Extract Vector Graphics via SVG Parsing ---
    print("\n--- Starting SVG-based Vector Extraction ---")
    vector_tags = {'path', 'line', 'rect', 'circle', 'ellipse', 'polyline', 'polygon'}
    vector_count = 0
    for page_index in range(len(doc)):
        page = doc[page_index]
        try:
            # Render page to SVG
            svg_data = page.get_svg_image(text_as_path=True)
            # Parse SVG XML
            root = ET.fromstring(svg_data)
            ns = {'svg': root.tag.split('}')[0].strip('{')}

            # Collect vector elements
            vectors = []
            for tag in vector_tags:
                vectors.extend(root.findall(f".//svg:{tag}", ns))

            if not vectors:
                print(f"No vector elements found on page {page_index+1}")
                continue

            # Build new SVG containing only vector shapes
            new_svg = ET.Element('svg', {
                'xmlns': 'http://www.w3.org/2000/svg',
                'width': root.get('width', ''),
                'height': root.get('height', ''),
                'viewBox': root.get('viewBox', '')
            })
            for elem in vectors:
                new_svg.append(elem)

            out_svg = ET.tostring(new_svg, encoding='unicode')
            fname = f"page_{page_index+1}_vectors.svg"
            fpath = os.path.join(vector_svgs_dir, fname)
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(out_svg)

            print(f"Extracted {len(vectors)} vector element(s) to: {fpath}")
            vector_count += 1
        except Exception as e:
            print(f"Error parsing SVG vectors on page {page_index+1}: {e}")
    print(f"--- Vector SVG pages extracted: {vector_count} ---")

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
