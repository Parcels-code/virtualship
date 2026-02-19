# File Permissions on the SURF RC Virtual Machine

The shared storage directory in the SURF RC virtual machine (e.g. `data/virtualship-storage/`) is configured such that all users of the workspace can read and access the files within it, but only the owner of a file can edit it. This can prevent seamless collaboration on the same expedition content, for example within your group.

## How to share and edit files within the shared storage

To enable collaboration on expedition content within your group, you can change the permissions of files within the shared storage directory to allow editing by all users. This can be done using the `chmod` command in the terminal (see [here](https://en.wikipedia.org/wiki/Chmod) for more detail on the `chmod` command).

For example, for your `expedition.yaml` file, you can run the following command in the terminal (after navigating to your group's directory and replacing `EXPEDITION_NAME` with your actual expedition directory):

```
chmod 777 /EXPEDITION_NAME/expedition.yaml
```

This will allow _all_ users in the SURF environment to edit the `expedition.yaml` file. You can repeat this process for any other files within the shared storage that you wish to collaborate on with your group members.

```{warning}
Be careful when using `chmod 777`, as it grants read, write, and execute permissions to **all** users. This means _everyone_ who has access to the SURF environment can edit the file (i.e. the whole class), which could cause accidental changes or deletions if not used carefully. We recommend you make backups of important files before changing permissions.

This is generally fine for the purposes of this unit where the virtual environment is a controlled setting, but in other contexts, it can pose security risks. Always ensure you understand the implications of changing file permissions and consider more restrictive permissions when necessary.

**TL;DR the `chmod 777` command is fine for this unit, but be very careful when using it in other contexts!**
```

## Reverting the file permissions

If you wish to revert the file permissions back to only allowing the owner to edit, you can run the following command in the terminal:

```
chmod 644 /EXPEDITION_NAME/expedition.yaml
```
