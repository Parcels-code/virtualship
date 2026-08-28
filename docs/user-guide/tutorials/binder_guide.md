# Post-processing Workspace Guide

This guide is supposed to be used once you have run VirtualShip simulations, which you may have done either on your own computer or in the VirtualShip workspace [via GitHub Codespaces](../user-profiles/educators/train-the-teacher/codespaces_guide.md).

The instructions below will guide you through the steps to access the VirtualShip post-processing workspace, upload your VirtualShip simulation output files, and run the example tutorials for analysis.

Using this workspace saves you from having to install any dependencies on your own computer. Note, if you plan for extensive post-processing analysis, you may prefer to move onto your own machine and install the dependencies there, as the Binder workspace is not suitable for long-running analysis (see [below](#non-persistent-storage)).

## Accessing the VirtualShip post-processing workspace

Navigate to the VirtualShip Workspace repository on GitHub: [https://github.com/j-atkins/virtualship-workspace](https://github.com/j-atkins/virtualship-workspace)

From here, on the repo welcome page, you should a section labelled **Workspace for VirtualShip post-processing - Binder**. Click on the **Step on Board: VirtualShip** button (Figure 1) to launch the post-processing workspace.

```{figure} ../_images/binder_button.png
:width: 200px
:align: center

<small>Figure 1. This button will launch the VirtualShip post-processing workspace via Binder.</small>
```

The first time you launch the workspace, the build will take a few minutes to complete (but should be faster on subsequent launches). Once the build is complete, you will be taken to a browser-based [JupyterLab](https://jupyterlab.readthedocs.io/en/stable/getting_started/overview.html) environment.

In the JupyterLab environment, you will see a file explorer on the left-hand side of the screen. You can use this to navigate the file structure of the workspace, and to upload/download files to/from your own computer.

You can also launch Terminal sessions to run commands in the workspace, and open Jupyter Notebooks to run the example tutorials (see [below](#running-the-example-tutorials)).

## Upload your VirtualShip output files

Before you can use the workspace to analyse your data, you will need to upload your VirtualShip simulation output files. You can do this via the file explorer in the JupyterLab environment. Simply navigate to the folder where you want to upload your files, and click the "Upload Files" button. Then select the files from your computer that you want to upload.

```{tip}
We suggest also making a new folder (called e.g. `data`) in the workspace to store your uploaded files, to keep things organised.
```

## Running the example tutorials

```{important}
The example tutorials are near-ready to be run 'out of the box'. However, you will have to adjust the file paths in the tutorial notebooks to point to your own data (e.g. in the `data` directory you may have created). As standard they have only have a place holder path, which will cause the code to fail.
```

There is a pre-uploaded folder called `tutorials` in the workspace (see in the file explorer, or you can navigate there in the Terminal with `cd tutorials`), which contains the example notebooks. These are mirrors of the tutorials in the [VirtualShip User Guide](../tutorials/index.md), and are provided here so that they can be run straight away with your data. There is one notebook dedicated to each of the instruments currently supported in VirtualShip.

You can open these in JupyterLab and run them as you would any other Jupyter Notebook. Simply click on them in the file explorer to open them and run through the cells. You can also edit the code in the notebooks to suit your own analysis needs.

## Non-persistent storage

The Binder workspace is not suitable for long-running analysis, as it has non-persistent storage. This means that any files you create or modify in the workspace will be lost when the workspace is closed and the notebook files will revert to the original version. Therefore it is intended as a space to run the example tutorials and do some quick analysis, but not for long-term storage of your data or results.

If you want to do more extensive analysis, we recommend that you download your data and results to your own computer, and run the analysis there. You will also need to install the required dependencies to your own computer.

```{tip}
A full list of dependencies is provided in the [environment.yml](https://github.com/j-atkins/virtualship-workspace/blob/main/.binder/environment.yml) file in the VirtualShip Workspace repository. You can use this file to install the dependencies on your own computer (e.g. with the `conda` [package manager](https://anaconda.org/channels/anaconda/packages/conda/overview)).
```
