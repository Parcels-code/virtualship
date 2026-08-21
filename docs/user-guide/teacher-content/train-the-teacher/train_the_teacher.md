# Train the teacher

We're pleased that you've chosen to use VirtualShip in your teaching! This guide is designed to help you get started with the platform and make the most of its features in your classroom.

The instructions are currently tailored primarily for educators at partner instutions, as part of the [VirtualShip NKO Scale Up project](https://virtualship.parcels-code.org/blog/scaleup-grant). However, we welcome all educators to explore the guide and adapt it to their own teaching contexts. For more tailored support, please see the [Feedback & support](#feedback-support) section at the end of this guide!

For this guide, we will assume that you're familiar with the purpose and motivations for using VirtualShip. We will be going through all the practical steps to get you up and running.

```{tip}
This is a long guide, intended as a blueprint for setting up your teaching... use the table of contents (on the right) to navigate to the sections that are most relevant to you!
```

## Foreword

### Introduction

As a reminder, where we refer to the VirtualShip Classroom, we refer to the combination of three core pillars: the `VirtualShip` software, VR / 360° videos and the Open Education Resources. The VirtualShip Classroom is designed to be flexible, the different components interchangable and can be used in a variety of ways, from highly structured to more open-ended activities. We discuss some example lesson plans [below](#lesson-plan-approaches), but we encourage you to adapt these to your own teaching context and learning objectives. As educators, we encourage you to think about the intended learning outcomes (ILOs) for your students and adapt the activities accoridingly.

### Our advice

In our experience, the most successful implementations of VirtualShip are those where the activities have a strong **narrative** ("You have been granted _ weeks of ship time!") and where students are given ample **freedom**, for example to choose their own research question, location and timing (perhaps from a selection of [case studies](../assignments/case_studies_virtualship.ipynb)).

```{note}
Check out evaluations of the VirtualShip Classroom in published paper(s) [here](https://virtualship.parcels-code.org/publications), for more information on the pedagogical approach!
```

That being said, the VirtualShip Classroom is a flexible platform and can be used in a variety of ways, from highly structured to more open-ended activities.

## Lesson plan approaches

The 'core' implementation of the VirtualShip Classroom has traditionally followed a structure of:

1. Background lecture on observing the ocean and research methods
2. Introduction to the VirtualShip software (if applicable)
3. In-class tutorials and exercises
4. Assignment hand-in (presentation or article) and feedback.

**More detail on all of these components (including links to lecture slides etc.) can be found in the [example lesson plans](lesson_plans.md) documentation.**

### Adding a VR component

The example lesson plans referred to above suggest including the VR component in your teaching. This is not a requirement, but we do recommend it as it can enhance the learning experience and provide students with a more immersive understanding of the challenges of sea-based research.

All the videos, available on [YouTube](https://www.youtube.com/@VirtualShipClassroom), can be viewed on students' own devices using their mouse to view in 360° if on a laptop/desktop or by moving their devices if watching on a mobile device. However, if the facilities exist at your instition, or you have access to VR headsets, you could use videos in a full VR environment. For more advice on how to set this up, please get in touch with the VirtualShip Team at [virtualship@uu.nl](mailto:virtualship.uu.nl).

<!-- TODO: probably better if we can provide more instruction, or link to instruction, here, e.g. the NIOZ Academy VR set up guide. -->

## Setting up a programming environment

```{tip}
If you are opting to use the VirtualShip Classroom without the `VirtualShip` software, there is no need to set up a programming environment for your students. You can refer to the Open Education Resources mentioned in the relevant [example lesson plan](./lesson_plans.md/#not-using-the-software) and/or the [VR component](#adding-a-vr-component) (if you choose to use it).

❗️ Please do still ask students to complete the end-of-course survey (see [below](#end-of-course-survey)) so that we can collect feedback on their experience with the VirtualShip Classroom.
```

There are broadly two ways to set up the `VirtualShip` software for teaching:

1. Each student uses a local installation of the software (on their own device), installed via a package manager such as `pip`, `conda` or `pixi`.
2. A software environment is pre-configured on a cloud-based platform.

Option 1) requires less preparation but can be more challenging for students to set up (especially if inexperienced) with frequent machine-dependent issues (and a lot of time spent on troubleshooting during lesson time!). Option 2) requires more preparation as the course convenor but is generally easier to support in-class, especially for larger groups. It also has the advantage that all students are working with the same resources, versions and infrastructure, which is beneficial for reproducibility and fairness.

In previous implementations at Utrecht University (where `VirtualShip` originated), we have primarily used Option 2) on the [SURF Research Cloud](https://www.surf.nl/en/services/compute/surf-research-cloud)).

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
If you have access to a computer lab, you may also consider installing the software on the those machines. This is similar to a local installation but can bring similar benefits to a cloud-based environment (i.e. each student has the same resources), but with less flexibility for students to work from home or on their own devices.
```

### Pre-configured environment (cloud based)

This documentation focuses on a set up specifically on the [SURF Research Cloud](https://www.surf.nl/en/services/compute/surf-research-cloud)). The concepts are similar for other cloud-based platforms, but you may need to adapt them to your own context.

```{note}
Note, the SURF Research Cloud is only available to Dutch institutions. Other cloud-based platforms (e.g. Google Colab, Binder, etc.) could be used as well but we have not extensively tested these platforms.
```

For detailed instructions on how to set up the pre-configured VirtualShip environment on the SURF Research Cloud, please refer to the set up guide below:

```{nbgallery}

surf_set_up.md
```

#### Student access to the workspace

When students log in to the SURF Research Cloud and click to access the workspace, they will be taken to a JupyterLab environment. This is where they can run the VirtualShip software and work on their expeditions.

```{important}
A known issue is that students may hit a server error when accessing the workspace. If this happens, keep on trying (refresh), as the server spin-up can be a bit overloaded at times, but should get through eventually.

Unfortunately this is out of our control. Clearing your browser cache and cookies, and/or trying via an incognito/private window may also help. We find that with persistence, the workspace will eventually load for all users.
```

We recommend distributing the following instructions sheet to your students once you have invited them to the workspace and ahead of first using the `VirtualShip` software, which outlines how to access the workspace and initialise the pre-configured environment in their respective account spaces:

```{nbgallery}

surf_student_access.md
```

```{note}
If you, as the course convenor/workspace owner, would also like to use the `VirtualShip` software, you will also need to carry out the steps in the instructions sheet above to initialise the environment in your own account space, as a one-time set up step.
```

#### Collaboration amongst students

We often recommend that students work in small groups (e.g. 2-3 students) for their VirtualShip projects. Each student should have their own account/access to the workspace and they can work from the same sub-directory in the `/data/{storage-name}` storage space.

Unfortunately, though, the SURF Research Cloud does not currently support smooth, simultaneous collaboration on the same files in the workspace. This means that students will need to coordinate amongst themselves to ensure that they are not overwriting each other's work. You can refer the students to the file permissions tutorial below for more information on how to arrange access to each other's files and directories in the workspace:

```{nbgallery}

file_permissions.md
```

## Sailing the ship

### Information on MFP

### Simulating Real Life Challenges

<!-- TODO -->

<!-- TODO: make a new branch which is dedicated to being the scale-up distributed one; with e.g. problems set to 'medium' as default -->
<!-- and then link to the instructions on getting touch with the VS team to update the software if this does not suit your teaching -->
<!-- and a tip that you can always override the problems module by using --difficulty-level easy -->
<!-- and that students may discover that you can override them once they explore the docs... if you need to ensure that they do encounter problems then we suggest making it a requirement in any assignment to discuss how they dealt with unexpected challenges -->

## ❗️ End-of-course survey

```{important}
We would be really grateful for your help in collecting feedback from your students on their experience with VirtualShip. This will help us to improve the platform, research its impact and to better understand how it is being used in different contexts.

<!-- TODO: add link! -->
Please distribute the following survey link to your students at the end of the course: _____
```

## Feedback & support

If you have any feedback on this guide, would like additional support or if you have suggestions for improvements, please reach out to us via our [GitHub issue tracker](https://github.com/Parcels-code/virtualship/issues) or by email: [virtualship@uu.nl](mailto:virtualship@uu.nl).

We are always happy to hear from educators and will do our best to support you in your teaching with VirtualShip!
