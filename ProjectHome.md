hardlink.py is a tool to hardlink together identical files in order to save space.  It is a complete rewrite and improvement over the original hardlink.c code (which was written by:  Jakub Jelinek <jakub@redhat.com>).  The purpose of the two is the same but they do it in vastly different ways.

This code has only been tested on Linux and should work on other Unix variants.  I have no idea if it will work on Windows as I have never tested it there and don't know about Windows support for hardlinks.

This code is very useful for people who mirror FTP sites in that it can save a large amount of space when you have identical files on the system.

I first wrote the code in C++ and then decided to port it to Python.

Performance is orders of magnitude faster than hardlink.c due to a more efficient algorithm.  Plus I think readability is much better too.



