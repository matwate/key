import openfoodfacts

api = openfoodfacts.API(user_agent="w2z/1,0")


def find_by_barcode(code):
    return api.product.get(code)


def find_by_text(text):
    return api.product.text_search(text)
