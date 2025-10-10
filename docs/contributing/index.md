# Contributing

All contributions are welcome no matter your background or experience! We collaborate on GitHub using issues to track bugs, features, and discuss future development. We use pull requests to collaborate on changes to the codebase (and modifications to the tutorials).

We have a design document providing a conceptual overview of VirtualShip. This document can be found [here](https://github.com/OceanParcels/virtualship/blob/main/design-doc.md). Suggested features will be worked on in a way that is consistent with the design document - but if you have suggestions on how we can improve the design of VirtualShip (e.g., to enable other features) please let us know!

## For developers

### Development installation

We use `conda` to manage our development installation. Make sure you have `conda` installed by following [the instructions here](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html) and then run the following commands:

```bash
conda create -n ship python=3.10
conda activate ship
conda env update --file environment.yml
pip install -e . --no-deps --no-build-isolation
```

This creates an environment, and installs all the dependencies that you need for development, including:

- core dependencies
- development dependencies (e.g., for testing)
- documentation dependencies

then installs the package in editable mode.

### Useful commands

The following commands are useful for local development:

- `pytest` to run tests
- `pre-commit run --all-files` to run pre-commit checks
- `pre-commit install` (optional) to install pre-commit hooks
  - this means that every time you commit, pre-commit checks will run on the files you changed
- `sphinx-autobuild docs docs/_build` to build and serve the documentation
- `sphinx-apidoc -o docs/api/ --module-first --no-toc --force src/virtualship` (optional) to generate the API documentation
- `sphinx-build -b linkcheck docs/ _build/linkcheck` to check for broken links in the documentation

The running of these commands is useful for local development and quick iteration, but not _vital_ as they will be run automatically in the CI pipeline (`pre-commit` by pre-commit.ci, `pytest` by GitHub Actions, and `sphinx` by ReadTheDocs).

## For maintainers

### Release checklist

- Go to GitHub, draft new release. Enter name of version and "create new tag" if it doesn't already exist. Click "Generate Release Notes". Currate release notes as needed. Look at a previous version release to match the format (title, header, section organisation etc.)
- Go to [conda-forge/virtualship-feedstock](https://github.com/conda-forge/virtualship-feedstock), create a new issue (select the "Bot Commands" issue from the menu) with title `@conda-forge-admin, please update version`. This will prompt a build, otherwise there can be a delay in the build.
  - Approve PR and merge on green
- Check "publish to PyPI" workflow succeeded

### Adding dependencies

When adding a dependency, make sure to modify the following files where relevant:

- `environment.yml` for core and development dependencies (important for the development environment, and CI)
- `pyproject.toml` for core dependencies (important for the pypi package, this should propagate through automatically to `recipe/meta.yml` in the conda-forge feedstock)
