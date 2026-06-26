import os


def configure_certifi():
    try:
        import certifi
    except ImportError:
        return
    cafile = certifi.where()
    os.environ.setdefault("SSL_CERT_FILE", cafile)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", cafile)
