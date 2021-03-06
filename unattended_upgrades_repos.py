#!/usr/bin/env python3
import os
import re
import sys
import fileinput
import shutil
import datetime
import signal
import logging
import logging.handlers
import subprocess
import optparse
# import apt_pkg


def main(options):
    STARTTIME = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    TARGETFILE = "/etc/apt/apt.conf.d/50unattended-upgrades"

    SKIPPED_RELEASES = []
    REPOS_TO_ADD = []

    # DISTRO_CODENAME = subprocess.check_output(
    #     ["lsb_release", "-c", "-s"], universal_newlines=True).strip()  # type: str
    # DISTRO_ID = subprocess.check_output(
    #     ["lsb_release", "-i", "-s"], universal_newlines=True).strip()  # type: str

    # SYSREPO_PATTERN = re.compile('.*o=' + DISTRO_ID + ',a=' + DISTRO_CODENAME + '.*')
    RELEASE_PATTERN = re.compile('\srelease (.*)\n')
    VALID_PATTERN = re.compile('.*(o=|a=|n=).*')

    # Get the repos
    APT_POLICY = subprocess.check_output(["apt-cache", "policy"]).decode('utf-8')
    RELEASES = re.findall(RELEASE_PATTERN, APT_POLICY)

    for RELEASE in RELEASES:
        RELEASE_SHORT = []
        RELEASE_SPLIT = RELEASE.split(",")
        for STRING in RELEASE_SPLIT:
            if re.search(VALID_PATTERN, STRING) is not None:
                RELEASE_SHORT.append(STRING)
        RELEASE_SHORT = ",".join(RELEASE_SHORT)
        # parse to get origin and suite
        try:
            if re.search(re.compile('.*o=.*'), RELEASE_SHORT) is not None:
                REPOS_TO_ADD.append('\t"' + RELEASE_SHORT + '";')
            else:
                SKIPPED_RELEASES.append(RELEASE_SHORT)
        except:
            SKIPPED_RELEASES.append(RELEASE_SHORT)

    # Only unique repos
    REPOS_TO_ADD = sorted(list(set(REPOS_TO_ADD)))

    # Checking if repos_to_add not already present  in /etc/apt/apt.conf.d/50unattended-upgrades
    with open(TARGETFILE, 'r') as f:
        READ_DATA = f.read()
        REPOS_ALREADY_PRESENT = re.findall('\t"o=.*";', READ_DATA)

    REPOS_TO_ADD = [repo for repo in REPOS_TO_ADD if repo not in REPOS_ALREADY_PRESENT]
    if REPOS_TO_ADD:
        while 1:
            if not options.quite:
                print("Repos to add:")
                print('\x1b[1;32;40m' + ''.join(REPOS_TO_ADD) + '\x1b[0m\n')
            if not options.add:
                print("Do you want to insert these into 50unattended-upgrades? [Y/n]")
                APPLYQUERY = input().lower()
            if options.add or APPLYQUERY == 'y' or APPLYQUERY == 'yes':
                if os.geteuid() != 0:
                    print("Didn't invoke as superuser.")
                    print('\x1b[1;31;40m' + "Do you want to elevate priviledges? [Y/n]" + '\x1b[0m')
                    UIDQUERY = input().lower()
                    if UIDQUERY == '' or UIDQUERY == 'y' or UIDQUERY == 'yes':
                        os.execvp("sudo", ["sudo"] + sys.argv + ["y"])
                    else:
                        print("Aborting.")
                        break
                else:
                    if not options.backup:
                        print("Create backup of current 50unattended-upgrades file? [Y/n]")
                        BACKUPQUERY = input().lower()
                        NOORIGINPATTERN = True
                    if options.backup or BACKUPQUERY == 'y' or BACKUPQUERY == 'yes':
                        shutil.copy2(TARGETFILE, TARGETFILE + "-" + STARTTIME + ".bak")
                    for line in fileinput.FileInput(TARGETFILE, inplace=1):
                        if "Unattended-Upgrade::Origins-Pattern {" in line:
                            NOORIGINPATTERN = False
                            line = line.replace(line, line + '\n'.join(REPOS_TO_ADD) + '\n')
                        print(line, end="")
                    if NOORIGINPATTERN:
                        APPENDORIGINS = open(TARGETFILE, 'a')
                        APPENDORIGINS.write('\n\nUnattended-Upgrade::Origins-Pattern {\n')
                        APPENDORIGINS.write("\n".join(REPOS_TO_ADD))
                        APPENDORIGINS.write('\n};')
                    break
            elif not options.add or APPLYQUERY == 'n' or APPLYQUERY == 'no':
                print("Not added.\n")
                break
            else:
                print("Please enter y/yes/CR or n/no\n")
    else:
        if not options.quite:
            print("No new Repos found.\n")

    if not options.quite and options.verbose and SKIPPED_RELEASES:
        print("Skipping files due to not present origin or suite. Or origin being a url.:")
        print('\x1b[1;32;40m' + ''.join(SKIPPED_RELEASES) + '\x1b[0m\n')
        if not REPOS_TO_ADD:
            print("\nNothing do to.")
    else:
        if not options.quite and not REPOS_TO_ADD:
            print("Nothing do to.")
    exit


def signal_handler(signal, frame):
    # type: (int, object) -> None
    logging.warning("SIGTERM received, will stop")
    global SIGNAL_STOP_REQUEST
    SIGNAL_STOP_REQUEST = True


if __name__ == "__main__":
    # init the options
    parser = optparse.OptionParser()
    parser.add_option("-d", "--debug",
                      action="store_true", default=False, dest='debug',
                      help=("print debug messages"))
    parser.add_option("-a", "--add",
                      action="store_true", default=False, dest='add',
                      help=("Add repos to allowed origins"))
    parser.add_option("-b", "--backup",
                      action="store_true", default=False, dest='backup',
                      help=("Create a backup of 50unattended-upgrades"))
    parser.add_option("-v", "--verbose",
                      action="store_true", default=False, dest='verbose',
                      help=("Verbose information"))
    parser.add_option("-q", "--quite",
                      action="store_true", default=False, dest='quite',
                      help=("No output (except errors)"))

    options, args = parser.parse_args()

    if os.getuid() != 0:
        print("You need to be root to run this application")
        sys.exit(1)

    # ensure that we are not killed when the terminal goes away e.g. on
    # shutdown
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    # setup signal handler for graceful stopping
    signal.signal(signal.SIGTERM, signal_handler)

    # run the main code
    main(options)
