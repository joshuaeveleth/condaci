#!/usr/bin/env python
import subprocess
import os
import os.path as p
from functools import partial


# forward stderr to stdout
co = partial(subprocess.check_output, stderr=subprocess.STDOUT)
check = partial(subprocess.check_call, stderr=subprocess.STDOUT)


def execute(cmd, verbose=False):
    r""" Runs a command, printing the command and it's output to screen.
    """
    if verbose:
        print('> {}'.format(' '.join(cmd)))
    result = co(cmd)
    if verbose:
        print(result)
    return result


def execute_sequence(*cmds, **kwargs):
    r""" Execute a sequence of commands. If any fails, display an error.
    """
    verbose = kwargs.get('verbose', True)
    try:
        for cmd in cmds:
            execute(cmd, verbose)
    except subprocess.CalledProcessError as e:
        print(' -> {}'.format(e.output))
        raise e


miniconda_dir = p.expanduser('~/miniconda')

# define our commands
miniconda_bin_dir = p.join(miniconda_dir, 'bin')
conda = p.join(miniconda_bin_dir, 'conda')
binstar = p.join(miniconda_bin_dir, 'binstar')
python = 'python'


def setup_miniconda(url, channel=None):
    print('Setting up miniconda from URL {}'.format(ns.path))
    miniconda_file = 'miniconda.sh'
    # TODO download with Python so we work on Windows.
    cmds =[['wget', '-nv', url, '-O', miniconda_file],
           [python, miniconda_file, '-b', '-p', miniconda_dir],
           [conda, 'update', '-q', '--yes', 'conda'],
           [conda, 'install', '-q', '--yes', 'conda-build', 'jinja2', 'binstar']]
    if channel is not None:
        print("(adding channel '{}' for dependencies)".format(channel))
        cmds.append([conda, 'config', '--add', 'channels', channel])
    else:
        print("No channels have been configured (all dependencies have to be "
              "sourceble from anaconda)")
    execute_sequence(*cmds)


def build(path):
    execute_sequence([conda, 'build', '-q', path])


def get_conda_build_path(path):
    from conda_build.metadata import MetaData
    from conda_build.build import bldpkg_path
    return bldpkg_path(MetaData(path))


def binstar_upload(key, user, channel, path):
    try:
        # TODO - could this safely be co? then we would get the binstar error..
        check([binstar, '-t', key, 'upload',
               '--force', '-u', user, '-c', channel, path])
    except subprocess.CalledProcessError as e:
        # mask the binstar key...
        cmd = e.cmd
        cmd[2] = 'BINSTAR_KEY'
        # ...then raise the error
        raise subprocess.CalledProcessError(e.returncode, cmd)


def build_and_upload(path, user=None, key=None):
    print('Building package at path {}'.format(ns.path))
    # actually issue conda build
    build(path)
    if key is None:
        print('No binstar key provided')
    if user is None:
        print('No binstar user provided')
    if user is None or key is None:
        print('-> Unable to upload to binstar')
        return
    # decide if we should attempt an upload
    if resolve_can_upload_from_travis():
        channel = resolve_channel_from_travis_state()
        print('Uploading to {}/{}'.format(user, channel))
        binstar_upload(key, user, channel, get_conda_build_path(path))


def resolve_can_upload_from_travis():
    is_a_pr = os.environ['TRAVIS_PULL_REQUEST'] == 'true'
    can_upload = not is_a_pr
    print("Can we can upload? : {}".format(can_upload))
    return can_upload


def resolve_channel_from_travis_state():
    branch = os.environ['TRAVIS_BRANCH']
    tag = os.environ['TRAVIS_TAG']
    print('Travis branch is "{}"'.format(branch))
    print('Travis tag found is: "{}"'.format(tag))
    if tag != '' and branch == tag:
        # final release, channel is 'main'
        print("on a tagged release -> upload to 'main'")
        return 'main'
    else:
        print("not on a tag on master - "
              "just upload to the branch name {}".format(branch))
        return branch


if __name__ == "__main__":
    from argparse import ArgumentParser
    parser = ArgumentParser(
        description=r"""
        Sets up miniconda, builds, and uploads to binstar on Travis CI.
        """)
    parser.add_argument("mode", choices=['setup', 'build'])
    parser.add_argument("--url", help="URL to download miniconda from "
                                      "(setup only, required)")
    parser.add_argument("-c", "--channel", help="binstar channel to activate "
                                                "(setup only, optional)")
    parser.add_argument("--path", "-p", help="path to the conda build "
                                             "scripts (build only, required)")
    parser.add_argument("-u", "--user", help="binstar user to upload to "
                                             "(build only, required to "
                                             "upload)")
    parser.add_argument("-k", "--key", help="The binstar key for uploading ("
                                            "build only, required to upload)")
    ns = parser.parse_args()

    if ns.mode == 'setup':
        url = ns.url
        if url is None:
            raise ValueError("You must provide a miniconda URL for the "
                             "setup command")
        setup_miniconda(url, channel=ns.channel)
    elif ns.mode == 'build':
        build_and_upload(ns.path, user=ns.user, key=ns.key)
