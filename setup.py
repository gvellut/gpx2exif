from setuptools import find_packages, setup

with open("gpx2exif/__init__.py") as f:
    for line in f:
        if line.find("__version__") >= 0:
            version = line.split("=")[1].strip()
            version = version.strip('"')
            version = version.strip("'")
            break

with open("README.md") as f:
    readme = f.read()

with open("requirements.txt") as f:
    requirements = f.readlines()

with open("requirements-dev.txt") as f:
    requirements_dev = f.readlines()

setup_args = dict(
    name="gpx2exif",
    version=version,
    description=(
        "Simple command-line tool to add GPS info from a GPX file "
        "to EXIF tags in images"
    ),
    long_description=readme,
    long_description_content_type="text/markdown",
    url="https://github.com/gvellut/gpx2exif",
    author="Guilhem Vellut",
    author_email="g@vellut.com",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Other Audience",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Topic :: Utilities",
    ],
    keywords="gpx gps exif tag",
    packages=find_packages(exclude=["docs", "tests"]),
    install_requires=requirements,
    extras_require={"dev": requirements_dev},
    project_urls={
        "Bug Reports": "https://github.com/gvellut/gpx2exif/issues",
        "Source": "https://github.com/gvellut/gpx2exif",
    },
    entry_points={"console_scripts": ["gpx2exif=gpx2exif.main:main"]},
)

setup(**setup_args)
