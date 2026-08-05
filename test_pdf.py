from fpdf import FPDF
pdf = FPDF()
pdf.add_page()
pdf.set_font("helvetica", size=12)
pdf.cell(200, 10, txt="Prueba áéíóú ñ", ln=1, align='C')
out = bytes(pdf.output())
print("Size:", len(out))
