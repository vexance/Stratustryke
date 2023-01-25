# Author: @vexance
# Purpose: Checks version against Git
# References: @zeroSteiner <

from __future__ import unicode_literals

__version__ = '0.0.1'
__progname__ = 'stratustryke'

import os
import subprocess

import smoke_zephyr.utilities

def get_revision():
	"""
	Retrieve the current git revision identifier. If the git binary can not be
	found or the repository information is unavailable, None will be returned.
	:return: The git revision tag if it's available.
	:rtype: str
	"""
	git_bin = smoke_zephyr.utilities.which('git')
	if not git_bin:
		return None
	proc_h = subprocess.Popen(
		(git_bin, 'rev-parse', 'HEAD'),
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		close_fds=True,
		cwd=os.path.dirname(os.path.abspath(__file__))
	)
	rev = proc_h.stdout.read().strip()
	proc_h.wait()
	if not len(rev):
		return None
	return rev.decode('utf-8')

revision = get_revision()