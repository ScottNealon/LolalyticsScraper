from pathlib import Path

from setuptools import find_packages, setup

with open(Path(__file__).parent.joinpath("requirements.txt"), "r") as file_handle:
    requirements = file_handle.readlines()

setup(
    name="lolalytics_scraper",
    package_dir=find_packages(),
    license="MIT",
    version="0.0",
    author="Scott Nealon",
    author_email="nealon.scott@gmail.com",
    install_requires=requirements,
    package_data={"lolalytics_scraper": ["data/*"]},
)
