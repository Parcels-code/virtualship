# Contributing

All contributions are welcome no matter your background or experience! We collaborate on GitHub using issues to track bugs, features, and discuss future development. We use pull requests to collaborate on changes to the codebase (and modifications to the tutorials).

We have a design document providing a conceptual overview of VirtualShip. This document can be found [here](https://github.com/OceanParcels/virtualship/blob/main/design-doc.md). Suggested features will be worked on in a way that is consistent with the design document - but if you have suggestions on how we can improve the design of VirtualShip (e.g., to enable other features) please let us know!

## For developers

### Development installation

```{note}
VirtualShip uses [Pixi](https://pixi.sh) to manage environments and run developer tooling. Pixi is a modern alternative to Conda and also includes other powerful tooling useful for a project like VirtualShip. It is our sole development workflow - we do not offer a Conda development workflow. Give Pixi a try, you won't regret it!
```

To get started contributing to VirtualShip:

**Step 1:** [Install Pixi](https://pixi.sh/latest/).

**Step 2:** [Fork the repository](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/fork-a-repo#forking-a-repository)

**Step 3:** Clone your fork and `cd` into the repository.

**Step 4:** Install the Pixi environment

```bash
pixi install
```

Now you have a development installation of VirtualShip, as well as a bunch of developer tooling to run tests, check code quality, and build the documentation! Simple as that.

### Pixi workflows

You can use the following Pixi commands to run common development tasks.

**Testing**

- `pixi run tests` - Run the full test suite using pytest with coverage reporting
- `pixi run tests-notebooks` - Run notebook tests

**Documentation**

- `pixi run docs` - Build the documentation using Sphinx
- `pixi run docs-watch` - Build and auto-rebuild documentation when files change (useful for live editing)

**Code quality**

- `pixi run lint` - Run pre-commit hooks on all files (includes formatting, linting, and other code quality checks)
- `pixi run typing` - Run mypy type checking on the codebase

**Different environments**

VirtualShip supports testing against different environments (e.g., different Python versions) with different feature sets. In CI we test against these environments, and you can too locally. For example:

- `pixi run -e test-py311 tests` - Run tests using Python 3.11
- `pixi run -e test-py312 tests` - Run tests using Python 3.12
- `pixi run -e test-latest tests` - Run tests using latest Python

The name of the workflow on GitHub contains the command you have to run locally to recreate the workflow - making it super easy to reproduce CI failures locally.

**Typical development workflow**

1. Make your code changes
2. Run `pixi run lint` to ensure code formatting and style compliance
3. Run `pixi run tests` to verify your changes don't break existing functionality
4. If you've added new features, run `pixi run typing` to check type annotations
5. If you've modified documentation, run `pixi run docs` to build and verify the docs

```{tip}
You can run `pixi info` to see all available environments and `pixi task list` to see all available tasks across environments.
```

## For maintainers

### Release checklist

- Go to GitHub, draft new release. Enter name of version and "create new tag" if it doesn't already exist. Click "Generate Release Notes". Currate release notes as needed. Look at a previous version release to match the format (title, header, section organisation etc.)
- Go to [conda-forge/virtualship-feedstock](https://github.com/conda-forge/virtualship-feedstock), create a new issue (select the "Bot Commands" issue from the menu) with title `@conda-forge-admin, please update version`. This will prompt a build, otherwise there can be a delay in the build.
  - Approve PR and merge on green
- Check "publish to PyPI" workflow succeeded

### Adding dependencies

When adding a dependency, make sure to modify the following files where relevant:

- `pixi.toml` for core and development dependencies (important for the development environment, and CI)
- `pyproject.toml` for core dependencies (important for the pypi package, this should propagate through automatically to `recipe/meta.yml` in the conda-forge feedstock)
