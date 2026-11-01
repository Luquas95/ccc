def test_package_importable():
    import ccc

    assert ccc.__version__  # stamped from the tag by the release build; "0.0.0-dev" otherwise
