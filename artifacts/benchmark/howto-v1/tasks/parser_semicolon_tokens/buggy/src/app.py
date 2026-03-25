def split_tokens(text):
    return [token.strip() for token in text.split(";") if token]
