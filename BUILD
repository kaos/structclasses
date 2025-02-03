python_distribution(
    name="dist",
    provides=python_artifact(name="structclasses"),
    dependencies=[":dist-files", "src/structclasses"],
    sdist=False,
    repositories=["@pypi"],
)

resources(
    name="dist-files",
    sources=[
        "pyproject.toml",
        "LICENSE",
        "README.md",
    ],
)
