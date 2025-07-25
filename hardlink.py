#!/usr/bin/python

# hardlink - Goes through a directory structure and creates hardlinks for
# files which are identical.
#
# Copyright (C) 2003 - 2010  John L. Villalovos, Hillsboro, Oregon
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc., 59
# Temple Place, Suite 330, Boston, MA  02111-1307, USA.
#
#
# ------------------------------------------------------------------------
# John Villalovos
# email: john@sodarock.com
# http://www.sodarock.com/
#
# Inspiration for this program came from the hardlink.c code. I liked what it
# did but did not like the code itself, to me it was very unmaintainable.  So I
# rewrote in C++ and then I rewrote it in python.  In reality this code is
# nothing like the original hardlink.c, since I do things quite differently.
# Even though this code is written in python the performance of the python
# version is much faster than the hardlink.c code, in my limited testing.  This
# is mainly due to use of different algorithms.
#
# Original inspirational hardlink.c code was written by:  Jakub Jelinek
# <jakub@redhat.com>
#
# ------------------------------------------------------------------------
#
# TODO:
#   *   Thinking it might make sense to walk the entire tree first and collect
#       up all the file information before starting to do comparisons.  Thought
#       here is we could find all the files which are hardlinked to each other
#       and then do a comparison.  If they are identical then hardlink
#       everything at once.

import hashlib
import os
import re
import stat
import sys
import time

from optparse import OptionParser

# Hash functions
# Create a hash from a file's size and time values
def hash_size_time(size, time):
    return (size ^ time) & (MAX_HASHES - 1);

def hash_size(size):
    return (size) & (MAX_HASHES - 1);

def hash_value(size, time, notimestamp):
    if notimestamp:
        return hash_size(size)
    else:
        return hash_size_time(size,time)

# Get the SHA1 hash of the specified file (identified by its device and inode).
# For performance, each inode is physically hashed once and the result is
# cached in the content_hashes dict.
def hash_content(file_info, options):
    stat_info = file_info[1]
    inode_key = stat_info[stat.ST_INO]
    sha1_value = content_hashes.get(inode_key)
    if not sha1_value:
        # Not in the dictionary, need to access the file
        file = open(file_info[0],'rb')
        m = hashlib.sha1()
        buffer_size = 1024*1024
        while 1:
            file_data = file.read(buffer_size)
            if not file_data:
                break
            m.update(file_data)
        sha1_value = m.digest()
        if options.verbose >= 2:
            print("Hashed file: %s" % file_info[0])
            print("     is    : %s" % m.hexdigest())
        # Cache the result in the dictionary
        content_hashes[inode_key] = sha1_value
        
    return sha1_value

# If two files have the same inode and are on the same device then they are
# already hardlinked.
def is_already_hardlinked(
    st1,     # first file's status
    st2 ):    # second file's status
    result = (
                      (st1[stat.ST_INO] == st2[stat.ST_INO]) and # Inodes equal
                      (st1[stat.ST_DEV] == st2[stat.ST_DEV])     # Devices equal
                  );
    return result

# Determine if a file is eligibile for hardlinking.  Files will only be
# considered for hardlinking if this function returns true.
def eligible_for_hardlink(
    st1,        # first file's status
    st2,        # second file's status
    options):

    result = (
            # Must meet the following
            # criteria:
            (not is_already_hardlinked(st1, st2)) and         # NOT already hard linked

            (st1[stat.ST_SIZE] == st2[stat.ST_SIZE]) and    # size is the same

            ((st1[stat.ST_MODE] == st2[stat.ST_MODE]) or
              (options.contentonly)) and                    # file mode is the same

            ((st1[stat.ST_UID] == st2[stat.ST_UID]) or      # owner user id is the same
              (options.contentonly)) and                    #   OR we are comparing content only

            ((st1[stat.ST_GID] == st2[stat.ST_GID]) or      # owner group id is the same
              (options.contentonly)) and                    #   OR we are comparing content only

            ((st1[stat.ST_MTIME] == st2[stat.ST_MTIME]) or  # modified time is the same
              (options.notimestamp) or                      #   OR date hashing is off
              (options.contentonly)) and                    #   OR we are comparing content only

            (st1[stat.ST_DEV] == st2[stat.ST_DEV]) and         # device is the same
            (st1[stat.ST_NLINK] + st2[stat.ST_NLINK] <= 65000) # linking these files will not exceed the maximum number of hardlinks on ext4
        )
    if None:
    # if not result:
        print("\n***\n", st1)
        print(st2)
        print("Already hardlinked: %s" % (not is_already_hardlinked(st1, st2)))
        print("Modes:", st1[stat.ST_MODE], st2[stat.ST_MODE])
        print("UIDs:", st1[stat.ST_UID], st2[stat.ST_UID])
        print("GIDs:", st1[stat.ST_GID], st2[stat.ST_GID])
        print("SIZE:", st1[stat.ST_SIZE], st2[stat.ST_SIZE])
        print("MTIME:", st1[stat.ST_MTIME], st2[stat.ST_MTIME])
        print("Ignore date:", options.notimestamp)
        print("Device:", st1[stat.ST_DEV], st2[stat.ST_DEV])
        if st1[stat.ST_NLINK] + st2[stat.ST_NLINK] > 65000:
            print("Too many hardlinks on this inode (more than 65000)")
            gStats.did_skip_beacuse_max_reached()
    return result


def are_file_contents_equal(filename1, filename2, options):
    """Determine if the contents of two files are equal.
    **!! This function assumes that the file sizes of the two files are
    equal."""
    # Open our two files
    file1 = open(filename1,'rb')
    file2 = open(filename2,'rb')
    # Make sure open succeeded
    if not (file1 and file2):
        print("Error opening file in are_file_contents_equal")
        print("Was attempting to open:")
        print("file1: %s" % filename1)
        print("file2: %s" % filename2)
        result = False
    else:
        if options.verbose >= 1:
            print("Comparing: %s" % filename1)
            print("     to  : %s" % filename2)
        buffer_size = 1024*1024
        while 1:
            # try added because the following triggers sometimes
            # a MemoryError
            try:
                buffer1 = file1.read(buffer_size)
                buffer2 = file2.read(buffer_size)
            except:
                print("Error while trying to compare files in are_file_contents_equal")
                print("Was attempting to open:")
                print("file1: %s" % filename1)
                print("file2: %s" % filename2)
                print("skipping comparison, i.e. no hardlink")
                result = False
                gStats.did_skip_beacuse_comparison_error()
                break
            if buffer1 != buffer2:
                result = False
                break
            if not buffer1:
                result = True
                break
        gStats.did_comparison()
    return result

# Determines if two files have the same hash value
def are_file_hashes_equal(file_info_1, file_info_2, options):
    return hash_content(file_info_1, options) == hash_content(file_info_2, options)

# Determines if two files should be hard linked together.
def are_files_hardlinkable(file_info_1, file_info_2, options):
    filename1 = file_info_1[0]
    stat_info_1 = file_info_1[1]
    filename2 = file_info_2[0]
    stat_info_2 = file_info_2[1]
    # See if the files are eligible for hardlinking
    if eligible_for_hardlink(stat_info_1, stat_info_2, options):
        result = True

        if options.samename:
            # Make sure the filenames are the same, if so then compare content
            basename1 = os.path.basename(filename1)
            basename2 = os.path.basename(filename2)
            if basename1 != basename2:
                result = False

        # Now see if the file content hashes the file are the same. If they
        # are then compare the contents.
        if result:
            result = are_file_hashes_equal(file_info_1, file_info_2, options)

        # Now see if the contents of the file are the same.  If they are then
        # these two files should be hardlinked.
        if result:
            result = are_file_contents_equal(filename1, filename2, options)
    else:
        result = False
    return result

# Hardlink two files together
def hardlink_files(sourcefile, destfile, stat_info, options):
    # rename the destination file to save it
    temp_name = destfile + ".$$$___cleanit___$$$"
    try:
        if not options.dryrun:
            os.rename(destfile, temp_name)
    except OSError as error:
        print("Failed to rename: %s to %s" % (destfile, temp_name))
        print(error)
        result = False
    else:
        # Now link the sourcefile to the destination file
        try:
            if not options.dryrun:
                os.link(sourcefile, destfile)
        except:
            print("Failed to hardlink: %s to %s" % (sourcefile, destfile))
            # Try to recover
            try:
                os.rename(temp_name, destfile)
            except:
                print("BAD BAD - failed to rename back %s to %s" % (temp_name, destfile))
            result = False
        else:
            # hard link succeeded
            # Delete the renamed version since we don't need it.
            if not options.dryrun:
                os.unlink ( temp_name)
            # update our stats
            gStats.did_hardlink(sourcefile, destfile, stat_info)
            if options.verbose >= 1:
                if options.dryrun:
                    print("Did NOT link.  Dry run")
                size = stat_info[stat.ST_SIZE]
                print("Linked: %s (already linked %s times)" % (sourcefile,stat_info[stat.ST_NLINK]))
                print("     to: %s, saved %s" % (destfile, size))
            result = True
    return result

def hardlink_identical_files(directories, filename, options):
    """
    The purpose of this function is to hardlink files together if the files are
    the same.  To be considered the same they must be equal in the following
    criteria:
          * file size
          * file contents
          * file mode (default)
          * owner user id (default)
          * owner group id (default)
          * modified time (default)

    Also, files will only be hardlinked if they are on the same device.  This
    is because hardlink does not allow you to hardlink across file systems.

    The basic idea on how this is done is as follows:

        Walk the directory tree building up a list of the files.

     For each file, generate a simple hash based on the size and modified time.

     For any other files which share this hash make sure that they are not
     identical to this file.  If they are identical then hardlink the files.

     Add the file info to the list of files that have the same hash value."""

    for exclude in options.excludes:
        if re.search(exclude, filename):
            return
    try:
        stat_info = os.stat(filename)
    except OSError:
        # Python 1.5.2 doesn't handle 2GB+ files well :(
        print("Unable to get stat info for: %s" % filename)
        print("If running Python 1.5 this could be because the file is greater than 2 Gibibytes")
        return
    if not stat_info:
        # We didn't get the file status info :(
        return

    # Is it a directory?
    if stat.S_ISDIR(stat_info[stat.ST_MODE]):
        # If it is a directory then add it to the list of directories.
        directories.append(filename)
    # Is it a regular file?
    elif stat.S_ISREG(stat_info[stat.ST_MODE]) and (stat_info[stat.ST_SIZE] >= options.minsize):
        # Create the hash for the file.
        file_hash = hash_value(stat_info[stat.ST_SIZE], stat_info[stat.ST_MTIME],
            options.notimestamp or options.contentonly)
        if debug1 or options.verbose >= 3: print("Fast hash done for %s" % filename)
        # Bump statistics count of regular files found.
        gStats.found_regular_file()
        if options.verbose >= 2:
            print("File: %s" % filename)
        work_file_info = (filename, stat_info)
        if file_hash in file_hashes:
            # We have file(s) that have the same hash as our current file.
            # Let's go through the list of files with the same hash and see if
            # we are already hardlinked to any of them.
            for (temp_filename,temp_stat_info) in file_hashes[file_hash]:
                if is_already_hardlinked(stat_info,temp_stat_info):
                    gStats.found_hardlink(temp_filename,filename,
                        temp_stat_info)
                    break
            else:
                # We did not find this file as hardlinked to any other file
                # yet.  So now lets see if our file should be hardlinked to any
                # of the other files with the same hash.
                for (temp_filename,temp_stat_info) in file_hashes[file_hash]:
                    if are_files_hardlinkable(work_file_info, (temp_filename, temp_stat_info),
                            options):
                        # The destfile will be the less linked file
                        if (stat_info[stat.ST_NLINK] > temp_stat_info[stat.ST_NLINK]):
                            destfile = temp_filename
                            used_stat_info = stat_info
                            sourcefile = filename
                            max_links = stat_info[stat.ST_NLINK]
                            min_links = temp_stat_info[stat.ST_NLINK]
                        else:
                            destfile = filename
                            used_stat_info = temp_stat_info
                            sourcefile = temp_filename
                            max_links = temp_stat_info[stat.ST_NLINK]
                            min_links = stat_info[stat.ST_NLINK]
                        if hardlink_files(sourcefile, destfile, used_stat_info, options):
                            if options.verbose >= 3:
                                print("source was: %s, with %s links" % (sourcefile,max_links))
                                print("   dest was: %s, with %s links" % (destfile,min_links))
                            # We need to refresh stats for both files
                            try:
                                new_stat_info = os.stat(sourcefile)
                            except OSError:
                                # Python 1.5.2 doesn't handle 2GB+ files well :(
                                print("Unable to get stat info for: %s" % filename)
                                print("If running Python 1.5 this could be because the file is greater than 2 Gibibytes")
                                return
                            if not new_stat_info:
                                # We didn't get the file status info :(
                                return
                            stat_info = new_stat_info
                            file_hashes[file_hash][0] = (sourcefile,new_stat_info)
                        break
                else:
                    # The file should NOT be hardlinked to any of the other
                    # files with the same hash.  So we will add it to the list
                    # of files.
                    file_hashes[file_hash].append(work_file_info)
        else:
            # There weren't any other files with the same hash value so we will
            # create a new entry and store our file.
            file_hashes[file_hash] = [work_file_info]
    elif debug1 or options.verbose >= 3: print("We skip (non regular or too small) for: %s" % filename)


class cStatistics:
    def __init__(self):
        self.dircount = 0                  # how many directories we find
        self.regularfiles = 0              # how many regular files we find
        self.comparisons = 0               # how many file content comparisons
        self.hardlinked_thisrun = 0        # hardlinks done this run
        self.hardlinked_previously = 0;    # hardlinks that are already existing
        self.bytes_saved_thisrun = 0       # bytes saved by hardlinking this run
        self.bytes_saved_previously = 0    # bytes saved by previous hardlinks
        self.hardlinkstats = []             # list of files hardlinked this run
        self.starttime = time.time()        # track how long it takes
        self.previouslyhardlinked = {}      # list of files hardlinked previously
        self.hardlinks_skipped = 0         # number of skipped hardlinks (to avoid errors)

    def found_directory(self):
        self.dircount = self.dircount + 1
    def found_regular_file(self):
        self.regularfiles = self.regularfiles + 1
    def did_comparison(self):
        self.comparisons = self.comparisons + 1
    def found_hardlink(self,sourcefile, destfile, stat_info):
        filesize = stat_info[stat.ST_SIZE]
        self.hardlinked_previously = self.hardlinked_previously + 1
        self.bytes_saved_previously = self.bytes_saved_previously + filesize
        if sourcefile not in self.previouslyhardlinked:
            self.previouslyhardlinked[sourcefile] = (stat_info,[destfile])
        else:
            self.previouslyhardlinked[sourcefile][1].append(destfile)
    def did_hardlink(self,sourcefile,destfile,stat_info):
        filesize = stat_info[stat.ST_SIZE]
        self.hardlinked_thisrun = self.hardlinked_thisrun + 1
        self.bytes_saved_thisrun = self.bytes_saved_thisrun + filesize
        self.hardlinkstats.append((sourcefile, destfile))
    def did_skip_beacuse_max_reached(self):
        self.hardlinks_skipped = self.hardlinks_skipped+1
    def did_skip_beacuse_comparison_error(self):
        self.hardlinks_skipped = self.hardlinks_skipped+1
    def print_stats(self, options):
        print("\n")
        print("Hard linking Statistics:")
        # Print out the stats for the files we hardlinked, if any
        if self.previouslyhardlinked and options.printprevious:
            keys = list(self.previouslyhardlinked.keys())
            keys.sort()
            print("Files Previously Hardlinked:")
            for key in keys:
                stat_info, file_list = self.previouslyhardlinked[key]
                size = stat_info[stat.ST_SIZE]
                print("Hardlinked together: %s" % key)
                for filename in file_list:
                    print("                   : %s" % filename)
                print("Size per file: %s  Total saved: %s" % (size,
                                    size * len(file_list)))
            print()
        if self.hardlinkstats:
            if options.dryrun:
                print("Statistics reflect what would have happened if not a dry run")
            print("Files Hardlinked this run:")
            for (source,dest) in self.hardlinkstats:
                print("Hardlinked: %s" % source)
                print("        to: %s" % dest)
            print()
        print("Directories                      : %s" % self.dircount)
        print("Regular files                    : %s" % self.regularfiles)
        print("Comparisons                      : %s" % self.comparisons)
        print("Hardlinked this run              : %s" % self.hardlinked_thisrun)
        print("Hardlinks skipped                : %s" % self.hardlinks_skipped)
        print("Total hardlinks                  : %s" % (self.hardlinked_previously + self.hardlinked_thisrun))
        print("Bytes saved this run             : %s (%s)" % (self.bytes_saved_thisrun, humanize_number(self.bytes_saved_thisrun)))
        totalbytes = self.bytes_saved_thisrun + self.bytes_saved_previously;
        print("Total bytes saved                : %s (%s)" % (totalbytes, humanize_number(totalbytes)))
        print("Total run time                   : %s seconds" % (time.time() - self.starttime))



def humanize_number( number ):
    if number  > 1024 ** 3:
        return ("%.3f gibibytes" % (number / (1024.0 ** 3)))
    if number  > 1024 ** 2:
        return ("%.3f mebibytes" % (number / (1024.0 ** 2)))
    if number  > 1024:
        return ("%.3f kibibytes" % (number / 1024.0))
    return ("%d bytes" % number)



def printversion(self):
    print("hardlink.py, Version %s" % VERSION)
    print("Copyright (C) 2003 - 2010 John L. Villalovos.")
    print("email: software@sodarock.com")
    print("web: http://www.sodarock.com/")
    print("""
This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; version 2 of the License.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE.  See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program; if not, write to the Free Software Foundation, Inc., 59 Temple
Place, Suite 330, Boston, MA  02111-1307, USA.
""")


def parse_command_line():
    usage = "usage: %prog [options] directory [ directory ... ]"
    version = "%prog: " + VERSION
    parser = OptionParser(usage=usage, version=version)
    parser.add_option("-f", "--filenames-equal", help="Filenames have to be identical",
        action="store_true", dest="samename", default=False,)

    parser.add_option("-n", "--dry-run", help="Do NOT actually hardlink files",
        action="store_true", dest="dryrun", default=False,)

    parser.add_option("-p", "--print-previous", help="Print previously created hardlinks",
        action="store_true", dest="printprevious", default=False,)

    parser.add_option("-q", "--no-stats", help="Do not print the statistics",
        action="store_false", dest="printstats", default=True,)

    parser.add_option("-t", "--timestamp-ignore",
        help="File modification times do NOT have to be identical",
        action="store_true", dest="notimestamp", default=False,)

    parser.add_option("-c", "--content-only",
        help="Only file contents have to match",
        action="store_true", dest="contentonly", default=False,)

    parser.add_option("-s", "--min-size",
        help="Minimum file size (default: %default)", metavar="SIZE",
        action="store", dest="minsize", type="int", default=1,)

    parser.add_option("-v", "--verbose",
        help="Verbosity level (default: %default)", metavar="LEVEL",
        action="store", dest="verbose", type="int", default=1,)

    parser.add_option("-x", "--exclude",
        help="Regular expression used to exclude files/dirs (may specify multiple times)", metavar="REGEX",
        action="append", dest="excludes", default=[],)

    (options, args) = parser.parse_args()
    if not args:
        parser.print_help()
        print()
        print("Error: Must supply one or more directories")
        sys.exit(1)
    args = [os.path.abspath(os.path.expanduser(dirname)) for dirname in args]
    for dirname in args:
        if not os.path.isdir(dirname):
            parser.print_help()
            print()
            print("Error: %s is NOT a directory" % dirname)
            sys.exit(1)

    if options.minsize < 1:
        parser.print_help()
        print()
        print("Error: minimum file size must be positive")
        sys.exit(1)

    return options, args


# Start of global declarations
debug = None
debug1 = None

MAX_HASHES = 128 * 1024

gStats = cStatistics()

file_hashes = {}
content_hashes = {}

VERSION = "0.05 - 2010-01-07 (07-Jan-2010)"

def main():
    # Parse our argument list and get our list of directories
    options, directories = parse_command_line()
    # Compile up our regexes ahead of time
    MIRROR_PL_REGEX = re.compile(r'^\.in\.')
    RSYNC_TEMP_REGEX = re.compile((r'^\..*\.\?{6,6}$'))
    # Now go through all the directories that have been added.
    # NOTE: hardlink_identical_files() will add more directories to the
    #       directories list as it finds them.
    while directories:
        # Get the last directory in the list
        directory = directories[-1] + '/'
        del directories[-1]
        if not os.path.isdir(directory):
            print("%s is NOT a directory!" % directory)
        else:
            gStats.found_directory()
            if debug1 or options.verbose >= 3: print("Working on directory %s" % directory)
            # Loop through all the files in the directory
            try:
                dir_entries = os.listdir(directory)
            except OSError:
                print("Error: Unable to do an os.listdir on: %s  Skipping..." % directory)
                continue
            for entry in dir_entries:
                pathname = os.path.normpath(os.path.join(directory,entry))
                # Look at files/dirs beginning with "."
                if entry[0] == ".":
                    # Ignore any mirror.pl files.  These are the files that
                    # start with ".in."
                    if MIRROR_PL_REGEX.match(entry):
                        continue
                    # Ignore any RSYNC files.  These are files that have the
                    # format .FILENAME.??????
                    if RSYNC_TEMP_REGEX.match(entry):
                        continue
                if os.path.islink(pathname):
                    if debug1 or options.verbose >= 3: print("%s: is a symbolic link, ignoring" % pathname)
                    continue
                if (debug1 or options.verbose >= 3) and os.path.isdir(pathname):
                    print("%s is a directory!" % pathname)
                hardlink_identical_files(directories, pathname, options)
    if options.printstats:
        gStats.print_stats(options)

if __name__ == '__main__':
    main()

