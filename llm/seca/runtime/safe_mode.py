SAFE_MODE = True


def assert_safe():
    if not SAFE_MODE:
        raise RuntimeError("Unsafe mode disabled in SAFE SECA v1")
