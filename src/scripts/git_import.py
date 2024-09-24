"""Generate and optionally execute Git commands to add files to a Git repository."""

import argparse
import glob
import logging
import os
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path

LOGGER = logging.getLogger(__name__)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] [%(name)s.%(funcName)s] %(message)s",
    level=logging.INFO,
)


def get_dates(file):
    """Read dates from a file."""
    date_format = "%Y-%m-%dT%H:%M:%S"
    in_date = False
    in_frontmatter = False
    frontmatter_marker = "---"
    results = {}
    with open(file) as fd:
        for line in fd.readlines():
            if not in_frontmatter and line.startswith(frontmatter_marker):
                in_frontmatter = True
                continue
            if in_frontmatter and line.startswith("date:"):
                in_date = True
                continue
            if in_date and line.startswith(("  created:", "  updated:")):
                type_, _, date = line.partition(":")
                results[type_.strip()] = datetime.strptime(date.strip(), date_format)
                continue
            if in_frontmatter and line.startswith(frontmatter_marker):
                break
    if not results:
        raise ValueError(f"Dates not found in the input file: {file}")
    return map(results.get, ["created", "updated"])


def exec_os_cmd(cmd, env, dry_run):
    """Execute an operating system command."""
    msg = f"{cmd=} {env=}"
    if dry_run:
        LOGGER.info(msg)
    else:
        LOGGER.debug(msg)
        try:
            proc = subprocess.run(
                cmd, capture_output=True, check=True, env=env, text=True
            )
            LOGGER.debug(proc)
        except subprocess.CalledProcessError as exc:
            LOGGER.error(
                f"Caught an error stdout={exc.stdout} stderr={exc.stderr} while executing a command {cmd}"
            )
            raise


def get_os_exec_env(date):
    """Get environment to execute OS commands."""
    env = os.environ.copy()
    date_format = "%Y-%m-%d %H:%M:%S"
    date_string = date.strftime(date_format)
    env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date_string
    return env


def get_posix_path(path):
    """Return an OS agnostic path with '/'."""
    return Path(path).as_posix()


def git_add_file(file, date, dry_run):
    """Add file to Git."""
    env = get_os_exec_env(date)
    cmd = 'git add "%s"' % (file)
    exec_os_cmd(cmd, env, dry_run)

    dir_ = os.path.splitext(file)[0]
    if os.path.isdir(dir_):
        cmd = 'git add "%s"' % (dir_)
        exec_os_cmd(cmd, env, dry_run)

    cmd = 'git commit -m "Add %s"' % (get_posix_path(file))
    exec_os_cmd(cmd, env, dry_run)


def git_update_file(file, date, dry_run):
    """Update an existing file in Git."""
    env = get_os_exec_env(date)
    cmd = 'git rm --cached "%s"' % (file)
    exec_os_cmd(cmd, env, dry_run)

    posix_path = get_posix_path(file)
    cmd = 'git commit -m "Updating %s"' % (posix_path)
    exec_os_cmd(cmd, env, dry_run)
    cmd = 'git add "%s"' % (file)
    exec_os_cmd(cmd, env, dry_run)
    cmd = 'git commit -m "Updating %s"' % (posix_path)
    exec_os_cmd(cmd, env, dry_run)


def git_import_file(file, dry_run):
    """Import single file."""
    created, updated = get_dates(file)
    LOGGER.debug(f"{created=} {updated=}")
    if created:
        git_add_file(file, created, dry_run)
    else:
        raise ValueError(f"The created date is not specified for a file: {file}")

    if updated:
        git_update_file(file, updated, dry_run)


def git_import(file_masks, dry_run):
    """Process input arguments."""
    found = False
    for file_mask in file_masks:
        for file in glob.glob(file_mask):
            git_import_file(file, dry_run)
            if not found:
                found = True
    if not found:
        raise ValueError(f"No file found matching pattern(s): {file_masks}")


def cli_main():
    """Command line entry point."""
    try:
        parser = argparse.ArgumentParser(prog="git_import", description=__doc__)
        parser.add_argument(
            "file_mask",
            nargs="+",
            help='Specify file mask(s) of the input files, e.g. "path/*.md"',
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Do not make any changes"
        )

        args = parser.parse_args()
        git_import(args.file_mask, args.dry_run)
    except Exception:
        sys.stderr.write(traceback.format_exc())
        return 255


if __name__ == "__main__":
    sys.exit(cli_main())
