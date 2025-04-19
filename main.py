import os
import fitz  # PyMuPDF
from tqdm import tqdm  # For progress bar
import xml.etree.ElementTree as ET

# Input PDF and output directory
pdf_path = '23-10-EG-400-A-b_STD60_Klima_W&MPlanung_20250207.pdf'
output_base = 'extracted_output'

# Create base output folder and SVG directory
os.makedirs(output_base, exist_ok=True)
svg_pages_dir = os.path.join(output_base, "svg_pages")
os.makedirs(svg_pages_dir, exist_ok=True)

print(f"Output directory created: {svg_pages_dir}")

def drawing_to_svg_path(drawing, clip_id=None):
    """Convert a drawing from page.get_drawings() to an SVG <path> element."""
    path_data = []
    for item in drawing.get("items", []):
        if item[0] == "l":  # Line
            p1, p2 = item[1], item[2]
            path_data.append(f"M{p1.x},{p1.y} L{p2.x},{p2.y}")
        elif item[0] == "c":  # Curve
            p1, p2, p3, p4 = item[1], item[2], item[3], item[4]
            path_data.append(f"M{p1.x},{p1.y} C{p2.x},{p2.y} {p3.x},{p3.y} {p4.x},{p4.y}")
        elif item[0] == "re":  # Rectangle
            rect = item[1]
            if not isinstance(rect, fitz.Rect):
                print(f"Unexpected type for rect: {type(rect)}")
                continue
            x, y, w, h = rect.x0, rect.y0, rect.width, rect.height
            path_data.append(f"M{x},{y} h{w} v{h} h{-w} z")

    if not path_data:
        return None

    # Get stroke and fill properties with robust checks
    stroke = drawing.get("color", [0, 0, 0])  # Default black
    stroke = f"rgb({int(stroke[0]*255)},{int(stroke[1]*255)},{int(stroke[2]*255)})" if isinstance(stroke, (list, tuple)) and len(stroke) == 3 else "none"
    fill = drawing.get("fill", None)
    fill = f"rgb({int(fill[0]*255)},{int(fill[1]*255)},{int(fill[2]*255)})" if fill and isinstance(fill, (list, tuple)) and len(fill) == 3 else "none"
    width = drawing.get("width", 1.0)
    opacity = drawing.get("stroke_opacity", 1.0)

    # Create SVG path element
    attribs = {
        "d": " ".join(path_data),
        "stroke": stroke,
        "fill": fill,
        "stroke-width": str(width),
        "stroke-opacity": str(opacity),
        "fill-opacity": str(drawing.get("fill_opacity", 1.0))
    }
    if clip_id:
        attribs["clip-path"] = f"url(#{clip_id})"
    path_elem = ET.Element("path", attribs)
    return path_elem

def create_clip_path(drawing, clip_id):
    """Create an SVG <clipPath> element from a drawing's clip or rect."""
    clip_path = ET.Element("clipPath", {"id": clip_id})
    if "rect" in drawing:
        rect = drawing["rect"]
        if not isinstance(rect, fitz.Rect):
            print(f"Unexpected type for rect in drawing: {type(rect)}")
            return None
        ET.SubElement(clip_path, "rect", {
            "x": str(rect.x0),
            "y": str(rect.y0),
            "width": str(rect.width),
            "height": str(rect.height)
        })
    elif "clip" in drawing:
        clip_rect = drawing["clip"].get("rect", None)
        if clip_rect and isinstance(clip_rect, fitz.Rect):
            ET.SubElement(clip_path, "rect", {
                "x": str(clip_rect.x0),
                "y": str(clip_rect.y0),
                "width": str(clip_rect.width),
                "height": str(clip_rect.height)
            })
        else:
            print(f"No valid clip rect found for drawing")
            return None
    # Return clip_path only if it has subelements
    if len(clip_path) > 0:  # Check if clip_path has any child elements
        return clip_path
    print(f"Clip path {clip_id} has no subelements, returning None")
    return None

try:
    # Open the PDF
    doc = fitz.open(pdf_path)
    print(f"Successfully opened PDF: {pdf_path} ({len(doc)} pages)")

    # Extract each page as SVG with all vector graphics
    print("\n--- Starting Page SVG Export ---")
    svg_count = 0
    for page_index in tqdm(range(len(doc)), desc="Exporting pages to SVG"):
        page = doc[page_index]
        try:
            # Generate base SVG with text as paths and embedded images
            svg_data = page.get_svg_image(text_as_path=True)
            svg_root = ET.fromstring(svg_data)

            # Create defs section for clip paths
            defs = ET.SubElement(svg_root, "defs")

            # Extract vector graphics
            drawings = page.get_drawings()
            vector_count = 0
            clip_count = 0
            for idx, drawing in enumerate(drawings):
                # Handle clipping paths
                clip_id = None
                if "rect" in drawing or "clip" in drawing:
                    clip_id = f"clip_{page_index+1}_{idx}"
                    clip_path = create_clip_path(drawing, clip_id)
                    if clip_path is not None:
                        defs.append(clip_path)
                        clip_count += 1
                    else:
                        print(f"Skipping clip path for drawing {idx} on page {page_index+1}")

                # Convert drawing to SVG path
                path_elem = drawing_to_svg_path(drawing, clip_id)
                if path_elem is not None:
                    svg_root.append(path_elem)
                    vector_count += 1

            print(f"Page {page_index+1}: Added {vector_count} vector paths, {clip_count} clip paths")

            # Save enhanced SVG
            fname = f"page_{page_index+1}.svg"
            fpath = os.path.join(svg_pages_dir, fname)
            with open(fpath, 'w', encoding='utf-8') as svg_file:
                svg_file.write(ET.tostring(svg_root, encoding='unicode'))
            print(f"Exported page {page_index+1} as SVG to: {fpath}")
            svg_count += 1
        except Exception as e:
            print(f"Error processing page {page_index+1}: {e}")
            continue
    print(f"--- Finished Page SVG Export ({svg_count} SVGs saved) ---")

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