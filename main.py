import fitz  # PyMuPDF
import base64, io
from xml.etree import ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)

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

        # 2) inject form XObjects (optional/fallback)
        embed_xobjects(svg_root, page, doc)

        # 3) write out
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
