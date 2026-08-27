# Train the teacher

We're pleased that you've chosen to use VirtualShip in your teaching! This guide is designed to help you get started with the platform and make the most of its features in your classroom. It binds different parts of the documentation together as a central blueprint for implementing the VirtualShip Classroom in your teaching.

The instructions are currently tailored primarily for educators at partner instutions, as part of the [VirtualShip NKO Scale Up project](https://virtualship.parcels-code.org/blog/scaleup-grant). However, we welcome all educators to explore the guide and adapt it to their own teaching contexts. For more tailored support, please see the [Feedback & support](#feedback-support) section at the end of this guide!

For this guide, we will assume that you're familiar with the purpose and motivations for using VirtualShip. We will be going through all the practical steps to get you up and running.

```{important}
No matter how you choose to implement the VirtualShip Classroom, we ask that you please ask your students to complete the end-of-course survey (see [below](#end-of-course-survey)) so that we can collect feedback on their experience with the VirtualShip Classroom.

This is really important for us to continue to research, evaluate and improve the VirtualShip Classroom! 🙂
```

## Foreword

### Introduction

As a reminder, where we refer to the VirtualShip Classroom, we refer to the combination of three core pillars: the `VirtualShip` software, VR / 360° videos and the Open Education Resources. The VirtualShip Classroom is designed to be flexible, the different components interchangable and can be used in a variety of ways, from highly structured to more open-ended activities.

We discuss some example lesson plans [below](#lesson-plans), but we encourage you to adapt these to your own teaching context and learning objectives. We don't intend for the guidance to be rigid and we encourage you to think about the intended learning outcomes (ILOs) for your students and adapt the activities accoridingly.

### Our advice

In our experience, the most successful implementations of VirtualShip are those where the activities have a strong **narrative** ("You have been granted _ weeks of ship time!") and where students are given ample **freedom**, for example to choose their own research question, location and timing (perhaps from a selection of [case studies](../../../assignments/case_studies_virtualship.ipynb)).

```{note}
Check out evaluations of the VirtualShip Classroom in published paper(s) [here](https://virtualship.parcels-code.org/publications), for more information on the pedagogical approach!
```

That being said, the VirtualShip Classroom is a flexible platform and can be used in a variety of ways, from highly structured to more open-ended activities.

## Lesson plans

The 'core' implementation of the VirtualShip Classroom has traditionally followed a structure of:

1. Background lecture on observing the ocean and research methods
2. Introduction to the VirtualShip software (if applicable)
3. In-class tutorials and exercises
4. Assignment hand-in (presentation or article) and feedback.

::::{grid} 1
:gutter: 4
:padding: 2 2 0 0
:class-container: sd-text-center

````{grid-item-card} Lesson plans 📖
:shadow: md

Click here for more detail on all of these components and some example lesson plans (including links to lecture slides and more).

+++

```{button-ref} lesson_plans
:ref-type: doc
:color: secondary
:expand:

Lesson plans
```
````

::::

```{tip}
No matter how you choose to implement the VirtualShip Classroom, it may be useful to check out some case study [examples](../../../assignments/case_studies_virtualship.ipynb) of research questions and expeditions that students could undertake.
```

### Code of conduct

If students are to work in groups, we recommend that you ask students to read, complete and sign the [Code of Conduct](../../../assignments/Code_of_conduct.ipynb) before starting their VirtualShip expeditions. This is to ensure that students are aware of the expectations for their behaviour and conduct during the course, and to promote a positive and respectful learning environment.

### Adding the VR / 360° videos component

The example lesson plans referred to above suggest including the VR component in your teaching. This is not a requirement, but we do recommend it as it can enhance the learning experience and provide students with a more immersive understanding of the challenges of sea-based research.

All the videos, available on [YouTube](https://www.youtube.com/@VirtualShipClassroom), can be viewed on students' own devices using their mouse to view in 360° if on a laptop/desktop or by moving their devices if watching on a mobile device. However, if the facilities exist at your instition, or you have access to VR headsets, you could use videos in a full VR environment. For more advice on how to arrange this, please get in touch with the VirtualShip Team at [virtualship@uu.nl](mailto:virtualship.uu.nl).

<!-- TODO: probably better if we can provide more instruction, or link to instruction, here, e.g. the NIOZ Academy VR set up guide. -->

## Setting up a programming environment

```{tip}
As mentioned in the [Lesson plans section](#lesson-plans), it is not necessary to use the `VirtualShip` software component as part of the VirtualShip Classroom. If this is the case, you can skip the next sections, and refer to the Open Education Resources mentioned in the relevant [example lesson plan](lesson_plans.md/#not-using-the-software).

❗️ Please do still ask students to complete the end-of-course survey (see [below](#end-of-course-survey)) though so that we can collect feedback on their experience with the VirtualShip Classroom.
```

There are broadly two ways to set up the `VirtualShip` software for teaching:

1. Each student uses a local installation of the software (on their own device), installed via a package manager such as `pip`, `conda` or `pixi`.
2. A software environment is pre-configured on a cloud-based platform/virtual machine.

Option 1) requires less preparation but can be more challenging for students to set up (especially if inexperienced) with frequent machine-dependent issues (and a lot of time spent on troubleshooting during lesson time!). Option 2) requires more preparation as the course convenor but is generally easier to support in-class, especially for larger groups. It also has the advantage that all students are working with the same resources, versions and infrastructure, which is beneficial for reproducibility and fairness.

```{important}
At present, for Option 2), we offer an _experimental_ pre-configured cloud-based environment solution via [GitHub Codespaces](https://github.com/features/codespaces) for VirtualShip simualtions (and [Binder](https://mybinder.org/) for a distributable post-processing space). This is a central, free solution that we can support and maintain, but it also has some limitations. Namely, each student must sign up for a GitHub account and the monthly free tier is limited to, in effect, 60 hours of usage (per student/GitHub account).

This will be sufficient for _most_ courses, but could be insufficient if your planned teaching activities are longer or more intensive. We continually monitor the optimum solution for distributing the VirtualShip software to whole classrooms in the most accessible way possible, and we are open to [feedback/advice](#feedback-support) on this.

**See the [Pre-configured environment (cloud based)](#pre-configured-environment-cloud-based) section below for more information on this option.**
```

### Local installation

Students can install the `VirtualShip` software on their own devices using `conda` from the command line:

```bash
# create a new conda environment called 'virtualship' and install the software from the conda-forge channel
conda create -n virtualship -c conda-forge virtualship

# activate the environment
conda activate virtualship
```

This creates an environment named `virtualship` with the latest version of the `VirtualShip` software installed. Students can then run the software from the command line in this environment.

```{tip}
If you have access to a computer lab, you may also consider installing the software on the those machines. This is similar to a local installation but can bring similar benefits to a cloud-based environment (i.e. the environment is prepared ahead of the lesson, each student has the same resources), but with less flexibility for students to work from home or on their own devices.
```

### Pre-configured environment (cloud based)

We provide a a pre-configured VirtualShip environment via GitHub Codespaces. Here, students will have access to the `VirtualShip` software and all its dependencies, without having to install anything on their own devices. This is a cloud-based solution, so students will need an internet connection and a GitHub account.

Below we provide a set of instructions which can be distributed to students, for them to get set up on the VirtualShip Workspace.

```{nbgallery}

../../../tutorials/codespaces_guide.md

```

```{tip}
Please don't hesitate to [get in touch](#feedback-support) if you have any problems with this approach or require additional support.
```

##### Collaboration within groups

_[This section is under development]_

<!-- TODO: populate this area when have explored how to facilitate collaboration within groups on Codespaces -->
<!-- TODO: note it is also referred to in the codespaces_guide.md so may not be 100% necessarily to separately distribute it -->

```{nbgallery}

collaboration.md
```

## Sailing the ship

Now that the technical set up is complete, we are ready to start getting students going with using the `VirtualShip` software! 🚢 🥳

The general-purpose **Quickstart guide** below provides a minimal overview of the basic commands and workflow to get started with the software... perhaps useful for you as the course convenor to get a quick overview of the software.

However, for teaching applications we recommend distributing the student-focused **"Sail the ship" guide** below, which is designed to be more accessible and includes additional context and narrative elements for students.

```{nbgallery}

../../../quickstart.md
../../../assignments/sail_the_ship.md

```

### Reviewing Expedition proposals

The "Sail the ship" guide above is designed to be used in conjunction with a lesson plan similar to that presented in the [example lesson plans](lesson_plans.md) documentation. It relies on students having already chosen a research question, submitting a proposal and having it approved by their instructor/you.

Reviewing and approving the proposals is a good time to check that students have a realistic plan for their expedition, and we find it is beneficial to prescribe a maximum ship time limit (e.g. 3 weeks) to ensure that students are thinking about the practicalities of their research question and sampling strategy.

```{tip}
The ship time limit can not currently be set in the `VirtualShip` software, but you could enforce it as part of your assignment instructions.
```

### Additional resources used in the VirtualShip workflow

You will notice in the "Quickstart" and "Sail the Ship" guides that there are a number of additional resources that get used in the VirtualShip workflow. These include the:

- [Copernicus Marine Data Store](https://data.marine.copernicus.eu/).
  - This source of the oceanographic data used in VirtualShip (streamed under-the-hood in the `VirtualShip` software).
  - As mentioned in the guides, students will need to set up a _free_ account to access the data. We recommend asking students to do this ahead of time, to avoid delays during the lesson.
  - Users are prompted to enter their credentials when they first run the `VirtualShip` software, and the credentials are then stored for future use.
- [Marine Facilities Planning (MFP) tool](https://nioz.marinefacilitiesplanning.com/cruiselocationplanning#)
  - This tool is used to plan the expedition route and generate the coordinates for the VirtualShip protocol.
  - It is an authentic tool used by real-life oceanographers to plan their research expedtions, and is a good example of the type of software that students may encounter in their future careers.
  - There is no sign-up required to use the tool, but students may need some time to get familiar with it.
  - As mentioned in the guides, the `VirtualShip` software can ingest exported coordinate files straight from MFP.

### Simulating Real Life Challenges

You will notice mentions to "Real Life Challenges" (RLCs) in the "Quickstart" and "Sail the Ship" guides. These are a module in the `VirtualShip` software that can be used to simulate real-life challenges that oceanographers may encounter during their research expeditions. These include things like equipment failures, bad weather, and other unexpected events. They usually require active intervention from the students to resolve.

They are not 'bugs' and are instead a feature that can be used to teach students about the challenges of oceanographic research: that things rarely go to plan, the scheudle will probably have to adapted and that some contingency planning is required.

The RLCs can be configured by setting the difficulty level (`--difficulty-level`) parameter in the virtualship run command. It can be set to `“easy”` (no problems, default in the main software distribution), `“medium”` or `“hard”` (e.g. `virtualship run EXPEDITION_NAME --difficulty-level medium`).

For maximum authenticity, you can set `--difficulty-level hard`, which will scale the number of problems encountered by the complexity of the expedition (longer duration, more waypoints, more instruments will lead to more problems). `--difficulty-level medium` will limit the number of problems to a maximum of 2, regardless of the expedition complexity.

```{tip}
We can arrange that the default difficulty level is set to `medium` for your course, if you would like to use the RLCs in your teaching without having to ask students to add the `--difficulty-level` parameter themselves on each run. This can enhance immersivity as the RLCs appear more unexpected from the students' perspective. Please [get in touch](#feedback-support) if this is something you would like to do.
```

```{note}
It's possible that students will explore this VirtualShip documentation site and understand that they can disable the RLCs by setting `--difficulty-level easy`. If you would like to ensure that students must encounter the RLCs, we suggest making a discussion of how they dealt with these issues part of their assignment. Similar to the ship time limit mentioned [previously](#reviewing-expedition-proposals).
```

### VirtualShip output

Once the simulations have run, the VirtualShip output files will be available in the workspace. These are in `.parquet` format.

```{tip}
`VirtualShip` depends heavily on `Parcels` under-the-hood for simulating the instrument behaviours. As such, the VirtualShip output is built on `Parcels` output formats. See the `Parcels` [documentation](https://docs.oceanparcels.org/en/main/user_guide/getting_started/tutorial_output.html) for more information on how to work with the `.parquet` files.
```

VirtualShip does not provide explicit tooling for analysis, as this will be dependent on the specific learning objectives and research questions of the students. However, we provide a number of **example tutorials**, which provide sample code for simple first analysis of the VirtualShip output, for each instrument type:

```{nbgallery}

../../../tutorials/index.md

```

#### Pre-configured post-processing workspace

We also host a VirtualShip post-processing environment via [Binder](https://mybinder.org/), which is a cloud-based Jupyter Notebook environment. This can be used to run the example tutorials and any other analysis code that students may wish to write, without having to install anything on their own devices. All relevant dependencies are pre-installed in this environment, the post-processing tutorials are directly available in the workspace, and the VirtualShip output files can be uploaded to the environment for analysis.

This is of course optional, but is offered as a means to make the post-processing analysis more accessible to students with less time spent setting up their local environment.

```{note}
This Binder environment is a separate workspace protocol to the GitHub Codespaces environment used for running the VirtualShip Simulations, and described [above](#pre-configured-environment-cloud-based). We made the decision to separate these two environments to minimise the amount of compute time on the Codespaces environment, which has a monthly limit per user.

The Binder environment does not have monthly quotas, but is not suitable for running the VirtualShip simulations themselves (low RAM and non-persistent storage). Hence the need (for now 🤞) to have these as two separate environments.
```

See the "Post-processing Workspace" guide below for more information on how to use this environment, and can also be distributed to students as part of your course.

<!-- TODO: this documentation needs to be written! -->

```{nbgallery}

../../../tutorials/binder_guide.md

```

## ❗️ End-of-course survey

```{important}
We would be really grateful for your help in collecting feedback from your students on their experience with VirtualShip. This will help us to improve the platform, research its impact and to better understand how it is being used in different contexts.

Please distribute the following survey link to your students at the end of the course: https://survey.uu.nl/jfe/form/SV_0OLu4lKYPyLhAxM
```

## Feedback & support

If you have any feedback on this guide, would like additional support or if you have suggestions for improvements, please reach out to us via our [GitHub issue tracker](https://github.com/Parcels-code/virtualship/issues) or by email: [virtualship@uu.nl](mailto:virtualship@uu.nl).

We are always happy to hear from educators and will do our best to support you in your teaching with VirtualShip!
