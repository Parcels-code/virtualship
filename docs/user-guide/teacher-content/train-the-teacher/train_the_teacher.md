# Train the Teacher

This guide is currently tailored primarily for educators at partner instutions, as part of the [VirtualShip NKO Scale Up project](https://virtualship.parcels-code.org/blog/scaleup-grant). However, we welcome all educators to explore the guide and adapt it to their own teaching contexts. For more tailored support, please see the [Feedback & support](#feedback-support) section at the end of this guide!

For this guide, we will assume that you're familiar with the purpose and motivations for using VirtualShip. We will be going through all the practical steps to get you up and running.

```{tip}
This is a long guide, intended as a blueprint for setting up your teaching... use the table of contents (on the right) to navigate to the sections that are most relevant to you!
```

```{important}
No matter how you choose to implement the VirtualShip Classroom, we ask that you please ask your students to complete the end-of-course survey (see [below](#end-of-course-survey)) so that we can collect feedback on their experience with the VirtualShip Classroom.

This is really important for us to continue to research, evaluate and improve the VirtualShip Classroom! 🙂
```

## Foreword

### Introduction

As a reminder, where we refer to the VirtualShip Classroom, we refer to the combination of three core pillars: the `VirtualShip` software, VR / 360° videos and the Open Education Resources. The VirtualShip Classroom is designed to be flexible, the different components interchangable and can be used in a variety of ways, from highly structured to more open-ended activities.

We discuss some example lesson plans [below](#lesson-plan-approaches), but we encourage you to adapt these to your own teaching context and learning objectives. We don't intend for the guidance to be rigid and we encourage you to think about the intended learning outcomes (ILOs) for your students and adapt the activities accoridingly.

### Our advice

In our experience, the most successful implementations of VirtualShip are those where the activities have a strong **narrative** ("You have been granted _ weeks of ship time!") and where students are given ample **freedom**, for example to choose their own research question, location and timing (perhaps from a selection of [case studies](../../assignments/case_studies_virtualship.ipynb)).

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

**More detail on all of these components (including links to lecture slides etc.) can be found in the [example lesson plans](lesson_plans.md) documentation.**

```{tip}
No matter how you choose to implement the VirtualShip Classroom, it may be useful to check out some case study [examples](../../assignments/case_studies_virtualship.ipynb) of research questions and expeditions that students could undertake.
```

### Adding the VR / 360° videos component

The example lesson plans referred to above suggest including the VR component in your teaching. This is not a requirement, but we do recommend it as it can enhance the learning experience and provide students with a more immersive understanding of the challenges of sea-based research.

All the videos, available on [YouTube](https://www.youtube.com/@VirtualShipClassroom), can be viewed on students' own devices using their mouse to view in 360° if on a laptop/desktop or by moving their devices if watching on a mobile device. However, if the facilities exist at your instition, or you have access to VR headsets, you could use videos in a full VR environment. For more advice on how to arrange this, please get in touch with the VirtualShip Team at [virtualship@uu.nl](mailto:virtualship.uu.nl).

<!-- TODO: probably better if we can provide more instruction, or link to instruction, here, e.g. the NIOZ Academy VR set up guide. -->

## Setting up a programming environment

```{tip}
As mentioned in the [Lesson plans section](#lesson-plans), it is not necessary to use the `VirtualShip` software component as part of the VirtualShip Classroom. If this is the case, you can skip the next sections, and refer to the Open Education Resources mentioned in the relevant [example lesson plan](./lesson_plans.md/#not-using-the-software).

❗️ Please do still ask students to complete the end-of-course survey (see [below](#end-of-course-survey)) though so that we can collect feedback on their experience with the VirtualShip Classroom.
```

There are broadly two ways to set up the `VirtualShip` software for teaching:

1. Each student uses a local installation of the software (on their own device), installed via a package manager such as `pip`, `conda` or `pixi`.
2. A software environment is pre-configured on a cloud-based platform.

Option 1) requires less preparation but can be more challenging for students to set up (especially if inexperienced) with frequent machine-dependent issues (and a lot of time spent on troubleshooting during lesson time!). Option 2) requires more preparation as the course convenor but is generally easier to support in-class, especially for larger groups. It also has the advantage that all students are working with the same resources, versions and infrastructure, which is beneficial for reproducibility and fairness.

In previous implementations at Utrecht University (where the VirtualShip Classroom originated), we have primarily used Option 2) on the [SURF Research Cloud](https://www.surf.nl/en/services/compute/surf-research-cloud).

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

This documentation focuses on a set up specifically on the [SURF Research Cloud](https://www.surf.nl/en/services/compute/surf-research-cloud)). The concepts are similar for other cloud-based platforms, but you may need to adapt them to your own context.

```{important}
Note, the SURF Research Cloud is only available to Dutch institutions. Other cloud-based platforms (e.g. Google Colab, Binder, etc.) could be used as well but we have not extensively tested these platforms.
```

For detailed instructions on how to set up the pre-configured VirtualShip environment on the SURF Research Cloud, please refer to the set up guide below:

```{nbgallery}

surf_set_up.md
```

#### Student access to the workspace

When students log in to the SURF Research Cloud and click to access the workspace, they will be taken to a JupyterLab environment. This is where they can run the VirtualShip software and work on their expeditions.

```{important}
A known issue is that students may hit a "server error" when accessing the workspace. If this happens, keep on trying (refresh), as the server spin-up can be a bit overloaded at times, but should get through eventually.

Unfortunately this is out of our control. Clearing your browser cache and cookies, and/or trying via an incognito/private window may also help. We find that with persistence, the workspace will eventually load for all users.
```

We recommend distributing the following instructions sheet to your students once you have invited them to the workspace and ahead of first using the `VirtualShip` software, which outlines how to access the workspace and initialise the pre-configured environment in their respective account spaces:

```{nbgallery}

surf_student_access.md
```

```{note}
If you, as the course convenor/workspace owner, would also like to use the `VirtualShip` software, you will also need to carry out the steps in the instructions sheet above to initialise the environment in your own account space, as a one-time set up step.
```

#### Collaboration within groups

We often recommend that students work in small groups (e.g. 2-3 students) for their VirtualShip projects. Each student should have their own account/access to the workspace and they can work from the same sub-directory in the `/data/{storage-name}` storage space.

Unfortunately, though, the SURF Research Cloud does not currently support smooth, simultaneous collaboration on the same files in the workspace. This means that students will need to coordinate amongst themselves to ensure that they are not overwriting each other's work. You can refer the students to the file permissions tutorial below for more information on how to arrange access to each other's files and directories in the workspace:

```{nbgallery}

file_permissions.md
```

## Sailing the ship

Now that the technical set up is complete, we are ready to start getting students going with using the `VirtualShip` software! 🚢 🥳

The general-purpose **Quickstart guide** below provides a minimal overview of the basic commands and workflow to get started with the software... perhaps useful for you as the course convenor to get a quick overview of the software.

However, for teaching applications we recommend distributing the student-focused **"Sail the ship" guide** below, which is designed to be more accessible and includes additional context and narrative elements for students.

```{nbgallery}

../../quickstart.md
../../assignments/sail_the_ship.md

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
We can arrange that the default difficulty level is set to `medium` for your course, if you would like to use the RLCs in your teaching without having to ask students to add the `--difficulty-level` parameter themselves on each run. This can enhance immersivity as the RLCs appear more unexpected from the students' perspective. Please [get in touch](train_the_teacher.md/#feedback-support) if this is something you would like to do.
```

```{note}
It's possible that students will explore this VirtualShip documentation site and understand that they can disable the RLCs by setting `--difficulty-level easy`. If you would like to ensure that students must encounter the RLCs, we suggest making a discussion of how they dealt with these issues part of their assignment. Similar to the ship time limit mentioned previously.
```

### VirtualShip output

Once the simulations have run, the VirtualShip output files will be available in the workspace. These are in `.parquet` format.

```{tip}
`VirtualShip` depends heavily on `Parcels` under-the-hood for simulating the instrument behaviours. As such, the VirtualShip output is built on `Parcels` output formats. See the `Parcels` [documentation](https://docs.oceanparcels.org/en/main/user_guide/getting_started/tutorial_output.html) for more information on how to work with the `.parquet` files.
```

VirtualShip does not provide explicit tooling for analysis, as this will be dependent on the specific learning objectives and research questions of the students. However, we have provided a number of **example tutorials** (see below), which provide sample code for simple first analysis of the VirtualShip output, for each instrument type.

```{nbgallery}

../../tutorials/index.md

```

We suggest that you encourage students to explore these tutorials and use them as a starting point for their own analysis. You might consider uploading copies of these notebooks to the shared storage space if you are using a cloud-based environment, so that students can access them without having to copy them from the documentation site. The easiest way to do so is to 'wget' the raw notebooks from the codebase, for example:

```bash

# copy the drifter data tutorial to the current directory
wget http://raw.githubusercontent.com/Parcels-code/virtualship/refs/heads/main/docs/user-guide/tutorials/Drifter_data_tutorial.ipynb
```

## ❗️ End-of-course survey

```{important}
We would be really grateful for your help in collecting feedback from your students on their experience with VirtualShip. This will help us to improve the platform, research its impact and to better understand how it is being used in different contexts.

Please distribute the following survey link to your students at the end of the course: https://survey.uu.nl/jfe/form/SV_0OLu4lKYPyLhAxM
```

## Feedback & support

If you have any feedback on this guide, would like additional support or if you have suggestions for improvements, please reach out to us via our [GitHub issue tracker](https://github.com/Parcels-code/virtualship/issues) or by email: [virtualship@uu.nl](mailto:virtualship@uu.nl).

We are always happy to hear from educators and will do our best to support you in your teaching with VirtualShip!
