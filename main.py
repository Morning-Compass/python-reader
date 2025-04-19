import os
import fitz  # PyMuPDF
from tqdm import tqdm
import xml.etree.ElementTree as ET
import base64
from io import BytesIO

# Input PDF and output directory
pdf_path = '23-10-EG-400-A-b_STD60_Klima_W&MPlanung_20250207.pdf'
output_base = 'extracted_output'

# Create base output folder and SVG directory
os.makedirs(output_base, exist_ok=True)
svg_pages_dir = os.path.join(output_base, "svg_pages")
os.makedirs(svg_pages_dir, exist_ok=True)

print(f"Output directory created: {svg_pages_dir}")

def drawing_to_svg_path(drawing, clip_id=None):
    path_data = []
    start_pt = None
    for item in drawing.get("items", []):
        op = item[0]
        if op == "m":
            p = item[1]
            start_pt = p
            path_data.append(f"M{p.x},{p.y}")
        elif op == "l":
            p2 = item[2]
            path_data.append(f"L{p2.x},{p2.y}")
        elif op == "c":
            p2, p3, p4 = item[2], item[3], item[4]
            path_data.append(f"C{p2.x},{p2.y} {p3.x},{p3.y} {p4.x},{p4.y}")
        elif op == "h":
            path_data.append("Z")
        elif op == "re":
            rect = item[1]
            if not isinstance(rect, fitz.Rect):
                print(f"Unexpected type for rect: {type(rect)}")
                continue
            x, y, w, h = rect.x0, rect.y0, rect.width, rect.height
            path_data.append(f"M{x},{y} h{w} v{h} h{-w} z")

    if not path_data:
        return None

    stroke = drawing.get("color", [0, 0, 0])
    stroke = (f"rgb({int(stroke[0]*255)},{int(stroke[1]*255)},{int(stroke[2]*255)})"
              if isinstance(stroke, (list, tuple)) and len(stroke) == 3 else "none")
    fill = drawing.get("fill", None)
    fill = (f"rgb({int(fill[0]*255)},{int(fill[1]*255)},{int(fill[2]*255)})"
            if isinstance(fill, (list, tuple)) and len(fill) == 3 else "none")
    width = drawing.get("width", 1.0)
    opacity = drawing.get("stroke_opacity", 1.0)

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

    return ET.Element("path", attribs)

def create_clip_path(drawing, clip_id):
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
        clip_rect = drawing["clip"].get("rect")
        if isinstance(clip_rect, fitz.Rect):
            ET.SubElement(clip_path, "rect", {
                "x": str(clip_rect.x0),
                "y": str(clip_rect.y0),
                "width": str(clip_rect.width),
                "height": str(clip_rect.height)
            })
        else:
            print(f"No valid clip rect found for drawing")
            return None
    return clip_path if len(clip_path) > 0 else None

try:
    doc = fitz.open(pdf_path)
    print(f"Successfully opened PDF: {pdf_path} ({len(doc)} pages)\n")

    print("--- Starting Page SVG Export ---")
    svg_count = 0

    for page_index in tqdm(range(len(doc)), desc="Exporting pages to SVG"):
        page = doc[page_index]
        try:
            svg_data = page.get_svg_image(text_as_path=True)
            svg_root = ET.fromstring(svg_data)

            # Ensure xlink namespace is present
            if "xmlns:xlink" not in svg_root.attrib:
                svg_root.attrib["xmlns:xlink"] = "http://www.w3.org/1999/xlink"

            # Parse or set viewBox
            viewbox = svg_root.attrib.get("viewBox")
            if viewbox:
                vb_x, vb_y, vb_w, vb_h = map(float, viewbox.strip().split())
            else:
                rect = page.rect
                vb_x, vb_y, vb_w, vb_h = rect.x0, rect.y0, rect.width, rect.height
                svg_root.attrib["viewBox"] = f"{vb_x} {vb_y} {vb_w} {vb_h}"

            # === STEP 1: Render PNG background scaled to viewBox ===
            zoom = 2
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            img_bytes = pix.tobytes("png")
            img_base64 = base64.b64encode(img_bytes).decode("utf-8")
            img_elem = ET.Element("image", {
                "x": str(vb_x), "y": str(vb_y),
                "width": str(vb_w), "height": str(vb_h),
                "preserveAspectRatio": "none",
                "{http://www.w3.org/1999/xlink}href": f"data:image/png;base64,{img_base64}"
            })

            # Insert image right after <defs> if it exists
            insert_index = 0
            for i, child in enumerate(svg_root):
                if child.tag.endswith('defs'):
                    insert_index = i + 1
                    break
            svg_root.insert(insert_index, img_elem)

            # === STEP 2: Add <defs> ===
            defs = ET.SubElement(svg_root, "defs")

            # === STEP 3: Vector drawings ===
            for idx, drawing in enumerate(page.get_drawings()):
                clip_id = None
                if "rect" in drawing or "clip" in drawing:
                    clip_id = f"clip_{page_index+1}_{idx}"
                    cp = create_clip_path(drawing, clip_id)
                    if cp is not None:
                        defs.append(cp)

                path_elem = drawing_to_svg_path(drawing, clip_id)
                if path_elem is not None:
                    svg_root.append(path_elem)

            # === STEP 4: Annotations ===
            for annot in page.annots() or []:
                subtype = annot.type[1]
                if subtype == "Line":
                    verts = annot.vertices
                    if len(verts) >= 2:
                        x1, y1 = verts[0].x, verts[0].y
                        x2, y2 = verts[1].x, verts[1].y
                        clr = annot.colors.get("stroke", [0, 0, 0])
                        stroke = f"rgb({int(clr[0]*255)},{int(clr[1]*255)},{int(clr[2]*255)})"
                        lw = annot.border_width or 1
                        attribs = {"x1": str(x1), "y1": str(y1), "x2": str(x2), "y2": str(y2),
                                   "stroke": stroke, "stroke-width": str(lw)}
                        svg_root.append(ET.Element("line", attribs))
                elif subtype in ("Ink", "Polyline"):
                    verts = annot.vertices
                    points = " ".join(f"{v.x},{v.y}" for v in verts)
                    clr = annot.colors.get("stroke", [0, 0, 0])
                    stroke = f"rgb({int(clr[0]*255)},{int(clr[1]*255)},{int(clr[2]*255)})"
                    lw = annot.border_width or 1
                    path = ET.Element("polyline", {"points": points,
                                                    "fill": "none",
                                                    "stroke": stroke,
                                                    "stroke-width": str(lw)})
                    svg_root.append(path)

            # === STEP 5: Save to disk ===
            out_file = os.path.join(svg_pages_dir, f"page_{page_index+1}.svg")
            with open(out_file, 'w', encoding='utf-8') as f:
                f.write(ET.tostring(svg_root, encoding='unicode'))
            svg_count += 1
            print(f"Exported page {page_index+1} → {out_file}")

        except Exception as e:
            print(f"Error on page {page_index+1}: {e}")
            continue

    print(f"--- Done ({svg_count}/{len(doc)} pages exported) ---")

except Exception as e:
    print(f"Fatal error: {e}")

finally:
    if 'doc' in locals() and doc:
        doc.close()
        print("PDF closed.")

print("Extraction finished.")
