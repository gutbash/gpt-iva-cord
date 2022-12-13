import latex2png

def latex_to_png(latex_string):
    png_image = latex2png.convert(latex_string)
    return png_image