# Learners

## Welcome aboard! 🚢

Welcome aboard the VirtualShip! Here you will conduct a research expedition in a digital replica of the global ocean. You'll plan your own expedition, choose where and when to sample, deploy oceanographic instruments (CTDs, Argo floats, drifters, ADCPs and more), and analyse the data you collect.

Along the way you'll find out how challenging it can be to measure the ocean. The software uses a digital twin of the ocean from the [Copernicus Marine Data Store](https://data.marine.copernicus.eu/products) alongside simulated instruments which behave as in real life.

## Sail the ship

The **Sail the Ship** guide is the main guide for your expedition. It takes you step by step from planning your route and configuring your instruments, to running the simulation and reporting your results.

::::{grid} 1
:gutter: 4
:padding: 2 2 0 0
:class-container: sd-text-center

````{grid-item-card} Sail the Ship 🚢
:shadow: md

Plan, configure and run your VirtualShip expedition, step by step.

+++

```{button-ref} ../../assignments/sail_the_ship
:ref-type: doc
:color: secondary
:expand:

Sail the Ship
```
````

::::

## Technical set up

### 1) Register with the Copernicus Marine Data Store

VirtualShip streams ocean data from the Copernicus Marine Data Store, so you will need a free [Copernicus Marine Service account](https://data.marine.copernicus.eu/register). Register before you start, because you will be asked for your credentials the first time you run an expedition.

### 2) Set up your programming environment

You will need a programming environment to run the VirtualShip software. Your instructor will give you more instructions but, otherwise, see the following options for how you can do this:

#### Option 1: with a pre-configured virtual machine

It is an option to use our **pre-configured cloud-based workspace** on [GitHub Codespaces](https://github.com/features/codespaces), which runs in your web browser and needs no local installation. All you need is a free GitHub account and an internet connection. Follow the Simulation Workspace Guide below to get started.

```{nbgallery}
---
maxdepth: 1
---
../../tutorials/codespaces_guide.md
```

```{important}
The free tier of GitHub Codespaces gives each account a limited number of hours per month. Remember to stop your Codespace when you're not using it so you don't use up your allowance (see the [Simulation Workspace Guide](../../tutorials/codespaces_guide.md) for details).
```

#### Option 2: install the software locally

```{note}
The instructions below use the [conda package manager](https://docs.conda.io/en/latest/) to install the software. If you don't have conda installed, you can download it from [here](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html). Also, see [here](https://docs.conda.io/projects/conda/en/stable/user-guide/getting-started.html) for a guide to using conda.
```

If your instructor has asked you to install the software on your own computer (or an institutional server) instead, you can create a new conda environment with `VirtualShip` installed as follows:

```bash
# create a new conda environment called 'virtualship' and install the software from the conda-forge channel
conda create -n virtualship -c conda-forge virtualship

# activate the environment
conda activate virtualship
```

### 3) Post-processing workspace

When your expedition has finished, you can analyse your results in our **post-processing workspace**. This is a separate, cloud-based JupyterLab environment (hosted on [Binder](https://mybinder.org/)) with all the analysis tools and example tutorials already installed. See the Post-processing Workspace Guide below for how to use it.

```{note}
You don't have to use the post-processing workspace. Feel free to download your data and analyse it in your own programming environment if you prefer.
```

```{nbgallery}
---
maxdepth: 1
---
../../tutorials/binder_guide.md
```

## Assignments

Your instructor will probably direct you to some of the assignments below as part of your course. You are welcome to browse them yourself here as well:

```{nbgallery}
---
maxdepth: 1
---
../educators/letter.md
../../assignments/case_studies_virtualship.ipynb
../../assignments/Research_proposal_intro.ipynb
../../assignments/Research_Proposal_only.ipynb
../../assignments/Virtualship_research_proposal.ipynb
../../assignments/sciencecommunication_assignment.ipynb
../../assignments/Code_of_conduct.ipynb
```

```{tip}
If you're working in a group, we suggest reading and signing the [Code of Conduct](../../assignments/Code_of_conduct.ipynb) with your team before you get started.
```

## Post-processing tutorials

Once you have completed your expedition, these tutorials show how to read in and plot the **output** from each `VirtualShip` instrument. Use them as a starting point for your own analysis.

```{nbgallery}
---
maxdepth: 1
---
../../tutorials/Drifter_data_tutorial.ipynb
../../tutorials/Argo_data_tutorial.ipynb
../../tutorials/CTD_transects.ipynb
../../tutorials/ADCP_transects.ipynb
../../tutorials/xbt_plotting.ipynb
../../tutorials/Ship_underwater_ST_plotting.ipynb
```

## End-of-course survey

The VirtualShip Classroom is developed by researchers at Utrecht University. At the end of your course, **please complete our short end-of-course survey**. Your experience and participation in the survey will help us improve the learning experience for future students 🙂

```{important}
Before taking part, please read the [**Research Participant Information Sheet**](../educators/information_sheet.md). It explains what taking part in the study involves, how your data will be used and stored, and your rights as a participant (taking part is voluntary).

Once you have finished all VirtualShip activities in your course, fill in the survey here: [**https://survey.uu.nl/jfe/form/SV_0OLu4lKYPyLhAxM**](https://survey.uu.nl/jfe/form/SV_0OLu4lKYPyLhAxM).
```

## Feedback & support

- **For questions about your course**, please ask your instructor first.
- **If you have any problems with the software**, or have feedback or suggestions for improvement, get in touch with the VirtualShip team via our [GitHub issue tracker](https://github.com/Parcels-code/virtualship/issues) or by email at [virtualship@uu.nl](mailto:virtualship@uu.nl).
- **For questions about the research study or your privacy**, see the contact details in the [information sheet](../educators/information_sheet.md).
