# Learner guide: Accessing the SURF Research Cloud

## Accepting SURF Research Cloud invite

In your student email you will have an invite from SURF Research Access Management (SRAM) to join a project on the SURF Research Cloud. Please accept this invite.

## Open the environment

Navigate to the [SURF Research Cloud Dashboard](https://portal.live.surfresearchcloud.nl/), or click on the link in the email, and click "access" on the shared workspace.

```{important}
A known issue is that you may hit a "server error" when accessing the workspace. If this happens, keep on trying (refresh), as the server spin-up can be a bit overloaded at times, but should get through eventually.

Unfortunately this is out of our control. Clearing your browser cache and cookies, and/or trying via an incognito/private window may also help. We find that with persistence, the workspace will eventually load.
```

## The JupyterLab workspace layout and additional config

```{note}
This only needs to be done once during setup!
```

In the JupyterLab workspace, you'll see the following (or similar) in your file explorer (left-hand side of the screen):

```
.
├── KERNEL-README.ipynb
├── data
│   └── datasets
|   └── virtualship-storage    <--- The shared persistent storage
└── scratch
```

```{note}
The persistent storage folder may be called something slightly different in your instance, for example it may have a name specific to the course you are enrolled on, such as `data/storage-osl`, `data/storage-dyoc` or `data/storage-1-sept`.
```

In the Jupyter launcher, you can open a Terminal session by clicking on "Terminal" button under the "Other" section, or by going to the "File" menu --> "New" --> "Terminal". From here you can navigate the workspace directory structure and run commands.

```{tip}
`VirtualShip` is a command line interface (CLI) based tool. We will be working predominantly via the command line in Terminal (typing out commands instead of pointing and clicking). If you are unfamiliar with what a CLI is, see [here](https://www.w3schools.com/whatis/whatis_cli.asp) for more information. In our case, the Terminal is just a way to access the CLI on the SURF Research Cloud virtual machine.
```

The `data/virtualship-storage` folder is your persistent storage. Here you can make a folder (e.g., by running `mkdir data/virtualship-storage/{your-group-name}` as a command in the Terminal, replacing `{your-group-name}` with your group name) to house your work for the unit. It is important to save all your work in this folder, so that it is still there the next time you log onto the remote workspace. This folder will be visible to anyone using the workspace, but only you will be able to make edits to it.

## Initialize conda

To be able to run VirtualShip from the Terminal, we need to take some additional steps. To make the already installed conda-tool available for yourself, you have to initialise your Terminal shell.

Back in the "Terminal" tab, type: `/etc/miniconda/bin/conda init`

Close the Terminal tab and start a new one.
You will see that the Terminal prompt has changed to something like

```bash
(base) metheuser@mywsp:
```

This is conda telling you that you are currently in the "base" environment.

From here, you already have another environment set up for you. Running `conda env list` in the Terminal, you should see:

```bash
conda env list

# conda environments:
#
base                 * /etc/miniconda
virtualship            /etc/miniconda/envs/virtualship`
```

Here you can do `conda activate virtualship` to activate the environment called "virtualship". This environment is a shared environment among all workspace users that can be centrally updated.

With the `virtualship` environment, you now have access to the `virtualship` command in your Terminal, which can be confirmed by running `virtualship --help`.

From here you can `cd` ('change directory') into `data/virtualship-storage/{your-group-name}` and run `virtualship` commands. You can now return to your course materials and follow the instructions to run the VirtualShip software.

## Extra tip: Working in Jupyter _Notebooks_

Finally, when you're working in Jupyter _Notebooks_ (`*.ipynb` files), you are able to access the conda environment with `virtualship` and related dependencies by switching the Kernel in the top right of the UI.
