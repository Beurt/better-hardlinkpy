 Better Hardlinkpy

Better Hardlinkpy is a fork of Hardlinkpy by @JohnVillalovos

This python 3 script optimizes space by grouping identical files (i.e. duplicates) with hardlinks (one single inode for many duplicate files).

 Original hardlinkpy

hardlink.py is a tool to hardlink together identical files in order to save space. It is a complete rewrite and improvement over the original hardlink.c code (which was written by: Jakub Jelinek jakub@redhat.com). The purpose of the two is the same but they do it in vastly different ways. This code has only been tested on Linux and should work on other Unix variants. It may work on Windows, but it was never tested. This code is very useful for people who mirror FTP sites in that it can save a large amount of space when you have identical files on the system.

@JohnVillalovos first wrote the code in C++ and then decided to port it to Python.

Performance is orders of magnitude faster than hardlink.c due to a more efficient algorithm. Plus @JohnVillalovos thinks readability is much better too.

The code was first imported from , but you can also find it on @JohnVillalovos repo:  (updated for Python 3.6).

 This fork: Better Hardlinkpy

 Merging several very old pull request

The original Hardlinkpy (on Google code) had several opened issues and several patch proposals. This fork includes the following:

• dealing with max hardlinks number: https://code.google.com/archive/p/hardlinkpy/issues/14 (included with some reporting)
• using hashes for comparisons that greatly (!!!) improves perfs, included from patch: https://code.google.com/archive/p/hardlinkpy/issues/11
• adding `--min-size` option (greatly improves perfs too), including the patch from: 
• triggering an exception when out of memory instead of crashing
• adding some more logging (in verbose mode 3)

 Algorithm improvements: merges new hardlink to old hardlinks

There was a difficult to explain issue with the original Hardlinkpy that was impeding compression efficiency, in particular when running several times the script on the same files.

The original Hardlinkpy was not efficient enough. It was checking files one by one and then recording them in memory. Once it picked a duplicate with one already in memory, it was hardlinking the files two by two (after some verification to confirm that they were identical).

Problem: sometimes (indeed often in my use case), the two identical files already had both hardlinks (i.e. they were two different inodes, with identical content, and each one had several files linked to it). Unfortunately, the original Hardlinkpy was hardlinking the currently tested file (e.g. inode1) to another duplicate inode already recorded in memory (e.g. inode2). So the duplicate was still here (e.g. inode1 and inode2 both existed, thus with identical content, and with files linked to them).

Consequences:

• There were still existing duplicates (and space lost): several different inodes pointing to identical files, each one having two or more hardlinks to files.
• Running the script twice or more on the same files was not grouping the inodes, but just "rolling" the hardlinks between inodes. Thus, there was no compression optimization while running the script twice. Hence, since the script was not backtracking the hardlinks, it was not possible to group all the duplicates on the same inode.

This fork, Better Hardlinkpy is more efficient. It is still not backtracking the links, but it improves the algorithm in order to group duplicates in the same inode, and enhances the grouping at each run of the script.

How? When two files with hardlinks are found equal, the inode chosen for the hardlink is the one having already the most links.

You can run the script several times; it will optimize the space grouping more and more identical hardlinks on the same inode.