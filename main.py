import fitz  # PyMuPDF
import base64, io
from xml.etree import ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)

def embed_images(svg_root, page, doc):
    """Extract each image on `page` and embed it as an <image> element."""
    for img in page.get_images(full=True):
        xref = img[0]
        # get its bbox
        try:
            rect = page.get_image_bbox(img)
        except Exception:
            continue
        # extract the raw image
        img_dict = doc.extract_image(xref)
        data = base64.b64encode(img_dict["image"]).decode("ascii")
        href = f"data:{img_dict['ext']};base64,{data}"
        attrib = {
            "x": str(rect.x0),
            "y": str(rect.y0),
            "width": str(rect.width),
            "height": str(rect.height),
            f"{{{XLINK_NS}}}href": href,
            "preserveAspectRatio": "none"
        }
        svg_root.append(ET.Element("image", attrib))

def embed_annots(svg_root, page):
    """Draw each annotation as a translucent rectangle and (optionally) text."""
    for annot in page.annots() or []:
        r = annot.rect
        # a translucent fill + border
        attrib = {
            "x": str(r.x0), "y": str(r.y0),
            "width": str(r.width), "height": str(r.height),
            "fill": "yellow", "fill-opacity": "0.2",
            "stroke": "orange", "stroke-width": "1"
        }
        svg_root.append(ET.Element("rect", attrib))
        # if the annot has popup text, include it
        content = annot.info.get("content")
        if content:
            txt = ET.Element("text", {
                "x": str(r.x0 + 2),
                "y": str(r.y0 + 12),
                "font-size": "10",
                "fill": "black"
            })
            txt.text = content
            svg_root.append(txt)

def embed_xobjects(svg_root, page, doc):
    """Extract Form XObjects (vector forms) and inject as <image>"""
    # note: most form XObjects are vectors; we rasterize them to embed
    for name, xref, typ in page.get_oc_items():
        # for OCG/OCMD entries; skip if not an XObject
        if typ != "ocg":
            continue
        try:
            # rasterize the form XObject at page resolution
            pix = page.get_pixmap(clip=page.annots())
            data = base64.b64encode(pix.tobytes()).decode("ascii")
            href = f"data:image/png;base64,{data}"
            attrib = {
                "x": "0", "y": "0",
                "width": str(page.rect.width),
                "height": str(page.rect.height),
                f"{{{XLINK_NS}}}href": href,
                "opacity": "0.5"
            }
            svg_root.append(ET.Element("image", attrib))
        except Exception:
            continue

def pdf_to_svg_full(pdf_path, output_prefix):
    doc = fitz.open(pdf_path)
    for i, page in enumerate(doc, start=1):
        # 1) get core SVG
        svg_bytes = page.get_svg_image(text_as_path=0)
        tree = ET.fromstring(svg_bytes)
        svg_root = tree

        # 2) inject images
        embed_images(svg_root, page, doc)
        # 3) inject annotations
        embed_annots(svg_root, page)
        # 4) inject form XObjects (optional/fallback)
        embed_xobjects(svg_root, page, doc)

        # 5) write out
        out_path = f"{output_prefix}_page{i}.svg"
        ET.ElementTree(svg_root).write(
            out_path, encoding="utf-8", xml_declaration=True
        )
        print("Wrote", out_path)
    doc.close()

if __name__ == "__main__":
    pdf_to_svg_full(
        "23-10-EG-400-A-b_STD60_Klima_W&MPlanung_20250207.pdf",
        "full_output"
    )
