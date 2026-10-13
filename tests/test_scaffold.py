def test_package_importable():
    import ccc

    assert ccc.__version__ == "0.1.0"
