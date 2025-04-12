from setuptools import setup, find_packages

setup(
    name="ovos-yaml-editor",
    version="0.0.1",
    description="Simple YAML editor for OpenVoiceOS with FastAPI backend",
    url="https://github.com/HiveMindInsiders/ovos-yaml-editor",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "uvicorn",
        "pyyaml",
        "ovos_config",
        "pydantic",
    ],
    entry_points={
        "console_scripts": [
            "ovos-yaml-editor = ovos_yaml_editor:main"
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
)
