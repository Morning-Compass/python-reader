import pymupdf  # PyMuPDF
import os
import xml.etree.ElementTree as ET # Import ElementTree for SVG manipulation

# --- Configuration ---
f_name = "23-10-EG-400-A-b_STD60_Klima_W&MPlanung_20250207.pdf"
output_dir = "extracted_svgs"  # Directory to save SVGs
# --- End Configuration ---

# Create the output directory if it doesn't exist
os.makedirs(output_dir, exist_ok=True)

print(f"--- Starting SVG Extraction for Regions of Images in {f_name} ---")
print(f"INFO: This extracts page regions containing images as SVG by setting the SVG viewBox.")
print(f"INFO: Output SVGs will visually clip to the image bounding box.")
print(f"INFO: Embedded raster images will remain raster within the SVG.")
# Note on 'static/' directory: This script generates SVGs. If used in a web app,
# you might move/copy these generated files to your web framework's 'static' directory later.

try:
    # Use a context manager for proper file handling
    with pymupdf.open(f_name) as doc:
        if doc.page_count == 0:
            print(f"Error: Document '{f_name}' contains no pages.")
            exit() # Exit if no pages

        # Process only the first page (index 0) - adjust if needed
        if doc.page_count > 0:
            page = doc[0]
            page_num = page.number # Use page.number for clarity in output

            # Get image list with full info needed for get_image_rects
            # full=True gives more details but basic xref is often enough if get_image_rects works
            image_list = page.get_images(full=True)

            if not image_list:
                print(f"No image instances found on page {page_num} of '{f_name}'.")
            else:
                print(f"Found {len(image_list)} image instances on page {page_num}. Extracting their regions as SVG...")

                # Generate the full-page SVG once for efficiency if manipulating it
                # If memory is a concern for huge pages, generate it inside the loop
                try:
                    full_page_svg_data = page.get_svg_image(text_as_path=False) # Often preferred over get_svg()
                except Exception as e_svg_gen:
                     print(f"ERROR generating base SVG for page {page_num}: {e_svg_gen}")
                     # Decide if you want to skip the page or try get_svg() as fallback
                     try:
                         print("WARN: Falling back to page.get_svg()")
                         full_page_svg_data = page.get_svg() # Fallback
                     except Exception as e_svg_gen_fallback:
                         print(f"ERROR generating base SVG with fallback for page {page_num}: {e_svg_gen_fallback}")
                         full_page_svg_data = None # Mark as failed

                if full_page_svg_data:
                    # Enumerate gives us an index 'i'
                    for i, img_info in enumerate(image_list):
                        xref = img_info[0]
                        img_instance_name = f"page_{page_num}_img_{i}_xref_{xref}"

                        try:
                            rects = page.get_image_rects(img_info)

                            if not rects:
                                print(f"  WARN: Could not find placement rectangle for image instance {i} (xref {xref}). Skipping.")
                                continue

                            # Process each rectangle where the image appears
                            for j, rect in enumerate(rects):
                                # Validate the rectangle
                                if rect.is_empty or not rect.is_valid or rect.width <= 0 or rect.height <= 0:
                                    print(f"  WARN: Skipping invalid/empty rectangle for image instance {i}, placement {j} (xref {xref}). Rect: {rect}")
                                    continue

                                # Generate a unique filename
                                # Add placement index 'j' if an image appears multiple times
                                placement_suffix = f"_placement_{j}" if len(rects) > 1 else ""
                                filename = os.path.join(output_dir, f"{img_instance_name}{placement_suffix}_region.svg")

                                try:
                                    # Parse the full page SVG XML
                                    # We need to encode to bytes for ET.fromstring
                                    root = ET.fromstring(full_page_svg_data.encode('utf-8'))

                                    # Modify the root <svg> tag's attributes to clip the view
                                    viewbox_val = f"{rect.x0} {rect.y0} {rect.width} {rect.height}"
                                    root.set('viewBox', viewbox_val)
                                    root.set('width', f"{rect.width}px")
                                    root.set('height', f"{rect.height}px")

                                    # Optional: Remove preserveAspectRatio to prevent scaling issues if original aspect ratio differs
                                    if 'preserveAspectRatio' in root.attrib:
                                        del root.attrib['preserveAspectRatio']

                                    # Serialize the modified XML back to a string
                                    # Use 'unicode' encoding for a standard UTF-8 string output
                                    clipped_svg_data = ET.tostring(root, encoding='unicode')

                                    # Save the modified SVG data string to a file
                                    with open(filename, "w", encoding="utf-8") as f_svg:
                                        f_svg.write(clipped_svg_data)
                                    print(f"  Saved SVG region: {filename} (viewBox: {viewbox_val})")

                                except ET.ParseError as e_xml:
                                    print(f"  ERROR: Failed to parse SVG XML for {img_instance_name}, placement {j}. Error: {e_xml}")
                                except Exception as e_manip:
                                     print(f"  ERROR: Failed during SVG manipulation for {img_instance_name}, placement {j}. Error: {e_manip}")

                        except Exception as e_rect:
                            # Catch potential errors during rect finding
                            print(f"ERROR processing rectangles for image instance {i} (xref {xref}): {e_rect}")
        else:
             print(f"Skipping document '{f_name}' as it has 0 pages after opening.")


except FileNotFoundError:
    print(f"Error: File not found at '{f_name}'")
except Exception as e_doc:
    # Catch-all for other issues like corrupt files, permission errors
    print(f"An unexpected error occurred opening or processing the PDF '{f_name}': {e_doc}")

print(f"--- SVG Extraction finished ---")