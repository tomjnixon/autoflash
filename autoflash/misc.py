def sha256(fname):
    import hashlib

    h = hashlib.sha256()
    with open(fname, "rb") as f:
        while block := f.read(1000000):
            h.update(block)
    return h.hexdigest()
