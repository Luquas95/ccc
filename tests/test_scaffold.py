def test_package_importable():
    import cc_continue

    assert cc_continue.__version__ == "0.1.0"
