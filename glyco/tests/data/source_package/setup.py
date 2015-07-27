from setuptools import setup

setup(
    name = "source_package",
    version = "0.0.1",
    author = "Philippe Gervais",
    author_email = "pgervais@google.com",
    description = "A small example test package.",
    keywords = "Simple example package",
    url = "https://chromium.googlesource.com/infra/infra.git/+/master/glyco/",
    packages=['source_package'],
    package_data={'source_package': ['*']}
)
