#!/usr/bin/python
# Copyright (c) 2010 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Smoke tests for gclient.py.

Shell out 'gclient' and run basic conformance tests.

This test assumes GClientSmokeBase.URL_BASE is valid.
"""

import logging
import os
import re
import subprocess
import sys
import unittest

from fake_repos import join, mangle_svn_tree, mangle_git_tree, write
from fake_repos import FakeReposTestBase

GCLIENT_PATH = join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'gclient')
COVERAGE = False


class GClientSmokeBase(FakeReposTestBase):
  def setUp(self):
    FakeReposTestBase.setUp(self)
    # Make sure it doesn't try to auto update when testing!
    self.env = os.environ.copy()
    self.env['DEPOT_TOOLS_UPDATE'] = '0'

  def gclient(self, cmd, cwd=None):
    if not cwd:
      cwd = self.root_dir
    if COVERAGE:
      # Don't use the wrapper script.
      cmd_base = ['coverage', 'run', '-a', GCLIENT_PATH + '.py']
    else:
      cmd_base = [GCLIENT_PATH]
    process = subprocess.Popen(cmd_base + cmd, cwd=cwd, env=self.env,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               shell=sys.platform.startswith('win'))
    (stdout, stderr) = process.communicate()
    return (stdout, stderr, process.returncode)


class GClientSmoke(GClientSmokeBase):
  def testHelp(self):
    """testHelp: make sure no new command was added."""
    result = self.gclient(['help'])
    self.assertEquals(1197, len(result[0]))
    self.assertEquals(0, len(result[1]))
    self.assertEquals(0, result[2])

  def testUnknown(self):
    result = self.gclient(['foo'])
    self.assertEquals(1197, len(result[0]))
    self.assertEquals(0, len(result[1]))
    self.assertEquals(0, result[2])

  def testNotConfigured(self):
    res = ('', 'Error: client not configured; see \'gclient config\'\n', 1)
    self.check(res, self.gclient(['cleanup']))
    self.check(res, self.gclient(['diff']))
    self.check(res, self.gclient(['export', 'foo']))
    self.check(res, self.gclient(['pack']))
    self.check(res, self.gclient(['revert']))
    self.check(res, self.gclient(['revinfo']))
    self.check(res, self.gclient(['runhooks']))
    self.check(res, self.gclient(['status']))
    self.check(res, self.gclient(['sync']))
    self.check(res, self.gclient(['update']))

  def testConfig(self):
    p = join(self.root_dir, '.gclient')
    def test(cmd, expected):
      if os.path.exists(p):
        os.remove(p)
      results = self.gclient(cmd)
      self.check(('', '', 0), results)
      self.checkString(expected, open(p, 'rb').read())

    test(['config', self.svn_base + 'trunk/src/'],
         'solutions = [\n'
         '  { "name"        : "src",\n'
         '    "url"         : "svn://127.0.0.1/svn/trunk/src",\n'
         '    "custom_deps" : {\n'
         '    },\n'
         '    "safesync_url": ""\n'
         '  },\n]\n')

    test(['config', self.git_base + 'repo_1', '--name', 'src'],
         'solutions = [\n'
         '  { "name"        : "src",\n'
         '    "url"         : "git://127.0.0.1/git/repo_1",\n'
         '    "custom_deps" : {\n'
         '    },\n'
         '    "safesync_url": ""\n'
         '  },\n]\n')

    test(['config', 'foo', 'faa'],
         'solutions = [\n'
         '  { "name"        : "foo",\n'
         '    "url"         : "foo",\n'
         '    "custom_deps" : {\n'
         '    },\n'
         '    "safesync_url": "faa"\n'
         '  },\n]\n')

    test(['config', '--spec', '["blah blah"]'], '["blah blah"]')

    os.remove(p)
    results = self.gclient(['config', 'foo', 'faa', 'fuu'])
    err = ('Usage: gclient.py config [options] [url] [safesync url]\n\n'
           'gclient.py: error: Inconsistent arguments. Use either --spec or one'
           ' or 2 args\n')
    self.check(('', err, 2), results)
    self.assertFalse(os.path.exists(join(self.root_dir, '.gclient')))


class GClientSmokeSVN(GClientSmokeBase):
  def setUp(self):
    GClientSmokeBase.setUp(self)
    self.FAKE_REPOS.setUpSVN()

  def testSync(self):
    # TODO(maruel): safesync.
    self.gclient(['config', self.svn_base + 'trunk/src/'])
    # Test unversioned checkout.
    results = self.gclient(['sync', '--deps', 'mac'])
    logging.debug(results[0])
    out = results[0].splitlines(False)
    self.assertEquals(17, len(out))
    self.checkString('', results[1])
    self.assertEquals(0, results[2])
    tree = mangle_svn_tree(
        (join('trunk', 'src'), 'src', self.FAKE_REPOS.svn_revs[-1]),
        (join('trunk', 'third_party', 'foo'), join('src', 'third_party', 'foo'),
            self.FAKE_REPOS.svn_revs[1]),
        (join('trunk', 'other'), join('src', 'other'),
            self.FAKE_REPOS.svn_revs[2]),
        )
    tree[join('src', 'svn_hooked1')] = 'svn_hooked1'
    self.assertTree(tree)

    # Manually remove svn_hooked1 before synching to make sure it's not
    # recreated.
    os.remove(join(self.root_dir, 'src', 'svn_hooked1'))

    # Test incremental versioned sync: sync backward.
    results = self.gclient(['sync', '--revision', 'src@1', '--deps', 'mac',
                            '--delete_unversioned_trees'])
    logging.debug(results[0])
    out = results[0].splitlines(False)
    self.assertEquals(19, len(out))
    self.checkString('', results[1])
    self.assertEquals(0, results[2])
    tree = mangle_svn_tree(
        (join('trunk', 'src'), 'src', self.FAKE_REPOS.svn_revs[1]),
        (join('trunk', 'third_party', 'foo'), join('src', 'third_party', 'fpp'),
            self.FAKE_REPOS.svn_revs[2]),
        (join('trunk', 'other'), join('src', 'other'),
            self.FAKE_REPOS.svn_revs[2]),
        (join('trunk', 'third_party', 'foo'),
            join('src', 'third_party', 'prout'),
            self.FAKE_REPOS.svn_revs[2]),
        )
    self.assertTree(tree)
    # Test incremental sync: delete-unversioned_trees isn't there.
    results = self.gclient(['sync', '--deps', 'mac'])
    logging.debug(results[0])
    out = results[0].splitlines(False)
    self.assertEquals(21, len(out))
    self.checkString('', results[1])
    self.assertEquals(0, results[2])
    tree = mangle_svn_tree(
        (join('trunk', 'src'), 'src', self.FAKE_REPOS.svn_revs[-1]),
        (join('trunk', 'third_party', 'foo'), join('src', 'third_party', 'fpp'),
            self.FAKE_REPOS.svn_revs[2]),
        (join('trunk', 'third_party', 'foo'), join('src', 'third_party', 'foo'),
            self.FAKE_REPOS.svn_revs[1]),
        (join('trunk', 'other'), join('src', 'other'),
            self.FAKE_REPOS.svn_revs[2]),
        (join('trunk', 'third_party', 'foo'),
            join('src', 'third_party', 'prout'),
            self.FAKE_REPOS.svn_revs[2]),
        )
    tree[join('src', 'svn_hooked1')] = 'svn_hooked1'
    self.assertTree(tree)

  def SyncAtRev1(self, arg):
    self.gclient(['config', self.svn_base + 'trunk/src/'])
    results = self.gclient(['sync', '--deps', 'mac', '-r', arg])
    out = results[0].splitlines(False)
    self.assertEquals(19, len(out))
    self.checkString('', results[1])
    self.assertEquals(0, results[2])
    tree = mangle_svn_tree(
        (join('trunk', 'src'), 'src', FAKE.svn_revs[1]),
        (join('trunk', 'third_party', 'foo'), join('src', 'third_party', 'fpp'),
            FAKE.svn_revs[2]),
        (join('trunk', 'other'), join('src', 'other'), FAKE.svn_revs[2]),
        (join('trunk', 'third_party', 'foo'),
            join('src', 'third_party', 'prout'),
            FAKE.svn_revs[2]),
        )
    self.assertTree(tree)

  def testSyncIgnoredSolutionName(self):
    self.SyncAtRev1('ignored@1')

  def testSyncNoSolutionName(self):
    self.SyncAtRev1('1')

  def testRevertAndStatus(self):
    self.gclient(['config', self.svn_base + 'trunk/src/'])
    # Tested in testSync.
    self.gclient(['sync', '--deps', 'mac'])
    write(join(self.root_dir, 'src', 'other', 'hi'), 'Hey!')

    results = self.gclient(['status'])
    out = results[0].splitlines(False)
    self.assertEquals(out[0], '')
    self.assertTrue(out[1].startswith('________ running \'svn status\' in \''))
    self.assertEquals(out[2], '?       svn_hooked1')
    self.assertEquals(out[3], '?       other')
    self.assertEquals(out[4], '?       third_party/foo')
    self.assertEquals(out[5], '')
    self.assertTrue(out[6].startswith('________ running \'svn status\' in \''))
    self.assertEquals(out[7], '?       hi')
    self.assertEquals(8, len(out))
    self.assertEquals('', results[1])
    self.assertEquals(0, results[2])

    # Revert implies --force implies running hooks without looking at pattern
    # matching.
    results = self.gclient(['revert'])
    out = results[0].splitlines(False)
    self.assertEquals(22, len(out))
    self.checkString('', results[1])
    self.assertEquals(0, results[2])
    tree = mangle_svn_tree(
        (join('trunk', 'src'), 'src', self.FAKE_REPOS.svn_revs[-1]),
        (join('trunk', 'third_party', 'foo'), join('src', 'third_party', 'foo'),
            self.FAKE_REPOS.svn_revs[1]),
        (join('trunk', 'other'), join('src', 'other'),
            self.FAKE_REPOS.svn_revs[2]),
        )
    tree[join('src', 'svn_hooked1')] = 'svn_hooked1'
    tree[join('src', 'svn_hooked2')] = 'svn_hooked2'
    self.assertTree(tree)

    results = self.gclient(['status'])
    out = results[0].splitlines(False)
    self.assertEquals(out[0], '')
    self.assertTrue(out[1].startswith('________ running \'svn status\' in \''))
    self.assertEquals(out[2], '?       svn_hooked1')
    self.assertEquals(out[3], '?       svn_hooked2')
    self.assertEquals(out[4], '?       other')
    self.assertEquals(out[5], '?       third_party/foo')
    self.assertEquals(6, len(out))
    self.checkString('', results[1])
    self.assertEquals(0, results[2])

  def testRevertAndStatusDepsOs(self):
    self.gclient(['config', self.svn_base + 'trunk/src/'])
    # Tested in testSync.
    self.gclient(['sync', '--deps', 'mac', '--revision', 'src@1'])
    write(join(self.root_dir, 'src', 'other', 'hi'), 'Hey!')

    results = self.gclient(['status', '--deps', 'mac'])
    out = results[0].splitlines(False)
    self.assertEquals(out[0], '')
    self.assertTrue(out[1].startswith('________ running \'svn status\' in \''))
    self.assertEquals(out[2], '?       other')
    self.assertEquals(out[3], '?       third_party/fpp')
    self.assertEquals(out[4], '?       third_party/prout')
    self.assertEquals(out[5], '')
    self.assertTrue(out[6].startswith('________ running \'svn status\' in \''))
    self.assertEquals(out[7], '?       hi')
    self.assertEquals(8, len(out))
    self.assertEquals('', results[1])
    self.assertEquals(0, results[2])

    # Revert implies --force implies running hooks without looking at pattern
    # matching.
    results = self.gclient(['revert', '--deps', 'mac'])
    out = results[0].splitlines(False)
    self.assertEquals(24, len(out))
    self.checkString('', results[1])
    self.assertEquals(0, results[2])
    tree = mangle_svn_tree(
        (join('trunk', 'src'), 'src', self.FAKE_REPOS.svn_revs[1]),
        (join('trunk', 'third_party', 'foo'), join('src', 'third_party', 'fpp'),
            self.FAKE_REPOS.svn_revs[2]),
        (join('trunk', 'other'), join('src', 'other'),
            self.FAKE_REPOS.svn_revs[2]),
        (join('trunk', 'third_party', 'prout'),
            join('src', 'third_party', 'prout'),
            self.FAKE_REPOS.svn_revs[2]),
        )
    self.assertTree(tree)

    results = self.gclient(['status', '--deps', 'mac'])
    out = results[0].splitlines(False)
    self.assertEquals(out[0], '')
    self.assertTrue(out[1].startswith('________ running \'svn status\' in \''))
    self.assertEquals(out[2], '?       other')
    self.assertEquals(out[3], '?       third_party/fpp')
    self.assertEquals(out[4], '?       third_party/prout')
    self.assertEquals(5, len(out))
    self.checkString('', results[1])
    self.assertEquals(0, results[2])

  def testRunHooks(self):
    self.gclient(['config', self.svn_base + 'trunk/src/'])
    self.gclient(['sync', '--deps', 'mac'])
    results = self.gclient(['runhooks'])
    out = results[0].splitlines(False)
    self.assertEquals(4, len(out))
    self.assertEquals(out[0], '')
    self.assertTrue(re.match(r'^________ running \'.*?python -c '
      r'open\(\'src/svn_hooked1\', \'w\'\)\.write\(\'svn_hooked1\'\)\' in \'.*',
      out[1]))
    self.assertEquals(out[2], '')
    # runhooks runs all hooks even if not matching by design.
    self.assertTrue(re.match(r'^________ running \'.*?python -c '
      r'open\(\'src/svn_hooked2\', \'w\'\)\.write\(\'svn_hooked2\'\)\' in \'.*',
      out[3]))
    self.checkString('', results[1])
    self.assertEquals(0, results[2])

  def testRunHooksDepsOs(self):
    self.gclient(['config', self.svn_base + 'trunk/src/'])
    self.gclient(['sync', '--deps', 'mac', '--revision', 'src@1'])
    results = self.gclient(['runhooks'])
    self.check(('', '', 0), results)

  def testRevInfo(self):
    # TODO(maruel): Test multiple solutions.
    self.gclient(['config', self.svn_base + 'trunk/src/'])
    self.gclient(['sync', '--deps', 'mac'])
    results = self.gclient(['revinfo'])
    out = ('src: %(base)s/src@2;\n'
           'src/other: %(base)s/other@2;\n'
           'src/third_party/foo: %(base)s/third_party/foo@1\n' %
          { 'base': self.svn_base + 'trunk' })
    self.check((out, '', 0), results)


class GClientSmokeGIT(GClientSmokeBase):
  def setUp(self):
    GClientSmokeBase.setUp(self)
    self.FAKE_REPOS.setUpGIT()

  def testSync(self):
    # TODO(maruel): safesync.
    self.gclient(['config', self.git_base + 'repo_1', '--name', 'src'])
    # Test unversioned checkout.
    results = self.gclient(['sync', '--deps', 'mac'])
    out = results[0].splitlines(False)
    # TODO(maruel): http://crosbug.com/3582 hooks run even if not matching, must
    # add sync parsing to get the list of updated files.
    self.assertEquals(13, len(out))
    self.assertTrue(results[1].startswith('Switched to a new branch \''))
    self.assertEquals(0, results[2])
    tree = mangle_git_tree(
        ('src', self.FAKE_REPOS.git_hashes['repo_1'][1][1]),
        (join('src', 'repo2'), self.FAKE_REPOS.git_hashes['repo_2'][0][1]),
        (join('src', 'repo2', 'repo_renamed'),
              self.FAKE_REPOS.git_hashes['repo_3'][1][1]),
        )
    tree[join('src', 'git_hooked1')] = 'git_hooked1'
    tree[join('src', 'git_hooked2')] = 'git_hooked2'
    self.assertTree(tree)

    # Manually remove git_hooked1 before synching to make sure it's not
    # recreated.
    os.remove(join(self.root_dir, 'src', 'git_hooked1'))

    # Test incremental versioned sync: sync backward.
    results = self.gclient(['sync', '--revision',
                            'src@' + self.FAKE_REPOS.git_hashes['repo_1'][0][0],
                            '--deps', 'mac', '--delete_unversioned_trees'])
    logging.debug(results[0])
    out = results[0].splitlines(False)
    self.assertEquals(20, len(out))
    self.checkString('', results[1])
    self.assertEquals(0, results[2])
    tree = mangle_git_tree(
        ('src', self.FAKE_REPOS.git_hashes['repo_1'][0][1]),
        (join('src', 'repo2'), self.FAKE_REPOS.git_hashes['repo_2'][1][1]),
        (join('src', 'repo2', 'repo3'),
            self.FAKE_REPOS.git_hashes['repo_3'][1][1]),
        (join('src', 'repo4'), self.FAKE_REPOS.git_hashes['repo_4'][1][1]),
        )
    tree[join('src', 'git_hooked2')] = 'git_hooked2'
    self.assertTree(tree)
    # Test incremental sync: delete-unversioned_trees isn't there.
    results = self.gclient(['sync', '--deps', 'mac'])
    logging.debug(results[0])
    out = results[0].splitlines(False)
    self.assertEquals(25, len(out))
    self.checkString('', results[1])
    self.assertEquals(0, results[2])
    tree = mangle_git_tree(
        ('src', self.FAKE_REPOS.git_hashes['repo_1'][1][1]),
        (join('src', 'repo2'), self.FAKE_REPOS.git_hashes['repo_2'][1][1]),
        (join('src', 'repo2', 'repo3'),
            self.FAKE_REPOS.git_hashes['repo_3'][1][1]),
        (join('src', 'repo2', 'repo_renamed'),
              self.FAKE_REPOS.git_hashes['repo_3'][1][1]),
        (join('src', 'repo4'), self.FAKE_REPOS.git_hashes['repo_4'][1][1]),
        )
    tree[join('src', 'git_hooked1')] = 'git_hooked1'
    tree[join('src', 'git_hooked2')] = 'git_hooked2'
    self.assertTree(tree)

  def testRevertAndStatus(self):
    """TODO(maruel): Remove this line once this test is fixed."""
    self.gclient(['config', self.git_base + 'repo_1', '--name', 'src'])
    # Tested in testSync.
    self.gclient(['sync', '--deps', 'mac'])
    write(join(self.root_dir, 'src', 'repo2', 'hi'), 'Hey!')

    results = self.gclient(['status'])
    out = results[0].splitlines(False)
    # TODO(maruel): http://crosbug.com/3584 It should output the unversioned
    # files.
    self.assertEquals(0, len(out))

    # Revert implies --force implies running hooks without looking at pattern
    # matching.
    results = self.gclient(['revert'])
    out = results[0].splitlines(False)
    # TODO(maruel): http://crosbug.com/3583 It just runs the hooks right now.
    self.assertEquals(7, len(out))
    self.checkString('', results[1])
    self.assertEquals(0, results[2])
    tree = mangle_git_tree(
        ('src', self.FAKE_REPOS.git_hashes['repo_1'][1][1]),
        (join('src', 'repo2'), self.FAKE_REPOS.git_hashes['repo_2'][0][1]),
        (join('src', 'repo2', 'repo_renamed'),
            self.FAKE_REPOS.git_hashes['repo_3'][1][1]),
        )
    # TODO(maruel): http://crosbug.com/3583 This file should have been removed.
    tree[join('src', 'repo2', 'hi')] = 'Hey!'
    tree[join('src', 'git_hooked1')] = 'git_hooked1'
    tree[join('src', 'git_hooked2')] = 'git_hooked2'
    self.assertTree(tree)

    results = self.gclient(['status'])
    out = results[0].splitlines(False)
    # TODO(maruel): http://crosbug.com/3584 It should output the unversioned
    # files.
    self.assertEquals(0, len(out))

  def testRunHooks(self):
    self.gclient(['config', self.git_base + 'repo_1', '--name', 'src'])
    self.gclient(['sync', '--deps', 'mac'])
    results = self.gclient(['runhooks'])
    logging.debug(results[0])
    out = results[0].splitlines(False)
    self.assertEquals(4, len(out))
    self.assertEquals(out[0], '')
    self.assertTrue(re.match(r'^________ running \'.*?python -c '
      r'open\(\'src/git_hooked1\', \'w\'\)\.write\(\'git_hooked1\'\)\' in \'.*',
    out[1]))
    self.assertEquals(out[2], '')
    # runhooks runs all hooks even if not matching by design.
    self.assertTrue(re.match(r'^________ running \'.*?python -c '
      r'open\(\'src/git_hooked2\', \'w\'\)\.write\(\'git_hooked2\'\)\' in \'.*',
      out[3]))
    self.checkString('', results[1])
    self.assertEquals(0, results[2])

  def testRevInfo(self):
    # TODO(maruel): Test multiple solutions.
    self.gclient(['config', self.git_base + 'repo_1', '--name', 'src'])
    self.gclient(['sync', '--deps', 'mac'])
    results = self.gclient(['revinfo'])
    out = ('src: %(base)srepo_1@%(hash1)s;\n'
           'src/repo2: %(base)srepo_2@%(hash2)s;\n'
           'src/repo2/repo_renamed: %(base)srepo_3@%(hash3)s\n' %
          {
            'base': self.git_base,
            'hash1': self.FAKE_REPOS.git_hashes['repo_1'][1][0],
            'hash2': self.FAKE_REPOS.git_hashes['repo_2'][0][0],
            'hash3': self.FAKE_REPOS.git_hashes['repo_3'][1][0],
          })
    self.check((out, '', 0), results)


class GClientSmokeBoth(GClientSmokeBase):
  def testMultiSolutions(self):
    self.gclient(['config', '--spec',
      'solutions=['
      '{"name": "src",'
      ' "url": "' + self.svn_base + 'trunk/src/"},'
      '{"name": "src-git",'
      '"url": "' + self.git_base + 'repo_1"}]'])
    results = self.gclient(['sync', '--deps', 'mac'])
    out = results[0].splitlines(False)
    self.assertEquals(32, len(out))
    # TODO(maruel): Something's wrong here. git outputs to stderr 'Switched to
    # new branch \'hash\''.
    #self.checkString('', results[1])
    self.assertEquals(0, results[2])
    tree = mangle_git_tree(
        ('src-git', FAKE.git_hashes['repo_1'][1][1]),
        (join('src', 'repo2'), FAKE.git_hashes['repo_2'][0][1]),
        (join('src', 'repo2', 'repo_renamed'), FAKE.git_hashes['repo_3'][1][1]),
        )
    tree.update(mangle_svn_tree(
        (join('trunk', 'src'), 'src', FAKE.svn_revs[2]),
        (join('trunk', 'third_party', 'foo'), join('src', 'third_party', 'foo'),
            FAKE.svn_revs[1]),
        (join('trunk', 'other'), join('src', 'other'), FAKE.svn_revs[2]),
        ))
    tree[join('src', 'git_hooked1')] = 'git_hooked1'
    tree[join('src', 'git_hooked2')] = 'git_hooked2'
    tree[join('src', 'svn_hooked1')] = 'svn_hooked1'
    tree[join('src', 'svn_hooked2')] = 'svn_hooked2'
    self.assertTree(tree)

  def testMultiSolutionsMultiRev(self):
    self.gclient(['config', '--spec',
      'solutions=['
      '{"name": "src",'
      ' "url": "' + self.svn_base + 'trunk/src/"},'
      '{"name": "src-git",'
      '"url": "' + self.git_base + 'repo_1"}]'])
    results = self.gclient(['sync', '--deps', 'mac', '--revision', '1', '-r',
                            'src-git@' + FAKE.git_hashes['repo_1'][0][0]])
    out = results[0].splitlines(False)
    self.assertEquals(35, len(out))
    # TODO(maruel): Something's wrong here. git outputs to stderr 'Switched to
    # new branch \'hash\''.
    #self.checkString('', results[1])
    self.assertEquals(0, results[2])
    tree = mangle_git_tree(
        ('src-git', FAKE.git_hashes['repo_1'][0][1]),
        (join('src', 'repo2'), FAKE.git_hashes['repo_2'][1][1]),
        (join('src', 'repo2', 'repo3'), FAKE.git_hashes['repo_3'][1][1]),
        (join('src', 'repo4'), FAKE.git_hashes['repo_4'][1][1]),
        )
    tree.update(mangle_svn_tree(
        (join('trunk', 'src'), 'src', FAKE.svn_revs[1]),
        (join('trunk', 'third_party', 'foo'), join('src', 'third_party', 'fpp'),
            FAKE.svn_revs[2]),
        (join('trunk', 'other'), join('src', 'other'), FAKE.svn_revs[2]),
        (join('trunk', 'third_party', 'foo'),
            join('src', 'third_party', 'prout'),
            FAKE.svn_revs[2]),
        ))
    self.assertTree(tree)


if __name__ == '__main__':
  if '-c' in sys.argv:
    COVERAGE = True
    sys.argv.remove('-c')
    if os.path.exists('.coverage'):
      os.remove('.coverage')
    os.environ['COVERAGE_FILE'] = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        '.coverage')
  unittest.main()