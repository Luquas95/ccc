# The release build (.github/workflows/release.yml) stamps the tag's version here;
# anything else — a checkout, a build made by hand — is "0.0.0-dev" and takes
# the newest tag of its checkout as its version (ccc.updates.installed_version).
__version__ = "0.0.0-dev"
