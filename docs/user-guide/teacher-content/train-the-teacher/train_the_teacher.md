# Train the teacher

We're pleased that you've chosen to use VirtualShip in your teaching!

This guide is designed to help you get started with the platform and make the most of its features in your classroom. It is currently tailored primarily for educators at partner instutions, as part of the [VirtualShip NKO Scale Up project](https://virtualship.parcels-code.org/blog/scaleup-grant). However, we welcome all educators to explore the guide and adapt it to their own teaching contexts.

Here, we will assume that you're familiar with the purpose and motivations for using VirtualShip. We will be going through all the practical steps to get you up and running.

```{tip}
This is a long guide... use the table of contents (on the right) to navigate to the sections that are most relevant to you!
```

## Foreword

In our experience, the most successful implementations of VirtualShip are those where the activities have a strong **narrative** ("You have been granted _ weeks of ship time!") and where students are given ample **freedom**, for example to choose their own research question, location and timing (perhaps from a selection of [case studies](../assignments/case_studies_virtualship.ipynb)).

That being said, VirtualShip is a flexible platform and can be used in a variety of ways, from highly structured to more open-ended activities.

## Setting up a programming environment

There are broadly two ways to set up VirtualShip for teaching:

1. Each student uses a local installation of the software (on their own device), installed via a package manager such as `pip`, `conda` or `pixi`.
2. A software environment is pre-configured on a cloud-based platform.

Option 1) requires less preparation but can be more challenging for students to set up (especially if inexperienced) with frequent machine-dependent issues (and a lot of time spent on troubleshooting during lesson time!). Option 2) requires more preparation as the course convenor but is generally easier to support in-class, especially for larger groups. It also has the advantage that all students are working with the same resources, versions and infrastructure, which is generally important for reproducibility and fairness.

In previous implementations at Utrecht University (where VirtualShip originated), we have primarily used Option 2) on the [SURF Research Cloud](https://www.surf.nl/en/services/compute/surf-research-cloud)).

### Local installation

<!-- TODO -->

```{tip}
If you have access to a computer lab, you may also consider installing the software on the those machines. This is similar to a local installation but can bring similar benefits to a cloud-based environment (i.e. each student has the same resources), but with less flexibility for students to work from home or on their own devices.
```

### Pre-configured environment (cloud based)

This documentation focuses on a set up specifically on the [SURF Research Cloud](https://www.surf.nl/en/services/compute/surf-research-cloud)). The concepts are similar for other cloud-based platforms, but you may need to adapt them to your own context.

```{note}
Note, the SURF Research Cloud is only available to Dutch institutions. Other cloud-based platforms (e.g. Google Colab, Binder, etc.) could be used as well but we have not extensively tested these platforms.
```

For detailed instructions on how to set up the pre-configured environment on the SURF Research Cloud, please refer to the SURF Research Cloud set up guide:

```{nbgallery}

surf_set_up.md
```

## Simulating Real Life Challenges

<!-- TODO -->

## ❗️ End-of-course survey

```{important}
We would be really grateful for your help in collecting feedback from your students on their experience with VirtualShip. This will help us to improve the platform, research its impact and to better understand how it is being used in different contexts.

Please distribute the following survey link to your students at the end of the course: _____
```

## Feedback

If you have any feedback on this guide, or if you have suggestions for improvements, please reach out to us via our [GitHub issue tracker](https://github.com/Parcels-code/virtualship/issues) or by email: [virtualship@uu.nl](mailto:virtualship@uu.nl).
