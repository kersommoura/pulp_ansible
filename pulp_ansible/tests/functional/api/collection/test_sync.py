# coding=utf-8
"""Tests related to sync ansible plugin collection content type."""
import unittest
from random import randint
from urllib.parse import urlsplit

from pulp_smash import api, config, cli
from pulp_smash.pulp3.constants import MEDIA_PATH, REPO_PATH
from pulp_smash.pulp3.utils import (
    gen_repo,
    get_added_content_summary,
    get_content_summary,
    get_removed_content_summary,
    sync,
)


from pulp_ansible.tests.functional.constants import (
    ANSIBLE_COLLECTION_FIXTURE_COUNT,
    ANSIBLE_COLLECTION_CONTENT_NAME,
    ANSIBLE_COLLECTION_REMOTE_PATH,
    ANSIBLE_COLLECTION_TESTING_URL,
    ANSIBLE_COLLECTION_FIXTURE_URL,
    ANSIBLE_REMOTE_PATH,
    ANSIBLE_FIXTURE_CONTENT_SUMMARY,
    ANSIBLE_COLLECTION_REQUIREMENT,
)
from pulp_ansible.tests.functional.utils import gen_ansible_remote
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class SyncTestCase(unittest.TestCase):
    """Sync the ansible plugin collections content type."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg)

    def test_sync(self):
        """Sync repository with the ansible plugin collections content type.

        This test targets the following issue:

        * `Pulp #4913 <https://pulp.plan.io/issues/4913>`_

        Do the following:

        1. Create a repository, and a remote.
        2. Assert that repository version is None.
        3. Sync the remote.
        4. Assert that repository version is not None.
        """
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo["_href"])

        body = gen_ansible_remote(url=ANSIBLE_COLLECTION_TESTING_URL)
        remote = self.client.post(ANSIBLE_COLLECTION_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote["_href"])

        # Sync the repository.
        self.assertIsNone(repo["_latest_version_href"], repo)
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo["_href"])
        self.assertIsNotNone(repo["_latest_version_href"], repo)

    def test_successive_syncs_repo_version(self):
        """Test whether successive syncs update repository versions.

        This test targets the following issue:

        * `Pulp #5000 <https://pulp.plan.io/issues/5000>`_

        Do the following:

        1. Create a repository, and a remote.
        2. Sync the repository an arbitrary number of times.
        3. Verify that the repository version is equal to the previous number
           of syncs.
        """
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo["_href"])

        body = gen_ansible_remote(url=ANSIBLE_COLLECTION_TESTING_URL)
        remote = self.client.post(ANSIBLE_COLLECTION_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote["_href"])

        number_of_syncs = randint(1, 5)
        for _ in range(number_of_syncs):
            sync(self.cfg, remote, repo)

        repo = self.client.get(repo["_href"])
        path = urlsplit(repo["_latest_version_href"]).path
        latest_repo_version = int(path.split("/")[-2])
        self.assertEqual(latest_repo_version, number_of_syncs, repo)

    def test_mirror_sync(self):
        """Sync multiple remotes into the same repo with mirror as `True`.

        This test targets the following issue: 5167

        * `<https://pulp.plan.io/issues/5167>`_

        This test does the following:

        1. Create a repo.
        2. Create two remotes
            a. Role remote
            b. Collection remote
        3. Sync the repo with Role remote.
        4. Sync the repo with Collection remote with ``Mirror=True``.
        5. Verify whether the content in the latest version of the repo
           has only Collection content and Role content is deleted.
        """
        # Step 1
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo["_href"])

        # Step 2
        role_remote = self.client.post(
            ANSIBLE_REMOTE_PATH, gen_ansible_remote())
        self.addCleanup(self.client.delete, role_remote["_href"])

        collection_remote = self.client.post(
            ANSIBLE_COLLECTION_REMOTE_PATH, gen_ansible_remote(
                url=ANSIBLE_COLLECTION_FIXTURE_URL)
        )
        self.addCleanup(self.client.delete, collection_remote["_href"])

        # Step 3
        sync(self.cfg, role_remote, repo)
        repo = self.client.get(repo["_href"])
        self.assertIsNotNone(repo["_latest_version_href"])
        self.assertDictEqual(get_added_content_summary(
            repo), ANSIBLE_FIXTURE_CONTENT_SUMMARY)

        # Step 4
        sync(self.cfg, collection_remote, repo, mirror=True)
        repo = self.client.get(repo["_href"])
        added_content_summary = get_added_content_summary(repo)
        self.assertGreaterEqual(
            added_content_summary[ANSIBLE_COLLECTION_CONTENT_NAME], ANSIBLE_COLLECTION_FIXTURE_COUNT
        )

        # Step 5
        content_summary = get_content_summary(repo)
        self.assertGreaterEqual(
            content_summary[ANSIBLE_COLLECTION_CONTENT_NAME], ANSIBLE_COLLECTION_FIXTURE_COUNT
        )
        self.assertDictEqual(get_removed_content_summary(
            repo), ANSIBLE_FIXTURE_CONTENT_SUMMARY)

    def test_mirror_sync_with_requirements(self):
        """
        Sync multiple remotes into the same repo with mirror as `True` using requirements.

        This test targets the following issue: 5250

        * `<https://pulp.plan.io/issues/5250>`_

        This test does the following:

        1. Create a repo.
        2. Create two remotes
            a. Role remote
            b. Collection remote
        3. Sync the repo with Role remote.
        4. Sync the repo with Collection remote with ``Mirror=True``.
        5. Verify whether the content in the latest version of the repo
            has only Collection content and Role content is deleted.
        """
        # Step 1
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo["_href"])

        # Step 2
        role_remote = self.client.post(
            ANSIBLE_REMOTE_PATH, gen_ansible_remote())
        self.addCleanup(self.client.delete, role_remote["_href"])

        collection_remote = self.client.post(
            ANSIBLE_COLLECTION_REMOTE_PATH,
            gen_ansible_remote(
                url=ANSIBLE_COLLECTION_TESTING_URL, requirements_file=ANSIBLE_COLLECTION_REQUIREMENT
            ),
        )

        self.addCleanup(self.client.delete, collection_remote["_href"])

        # Step 3
        sync(self.cfg, role_remote, repo)
        repo = self.client.get(repo["_href"])
        self.assertIsNotNone(repo["_latest_version_href"], repo)
        self.assertDictEqual(get_added_content_summary(
            repo), ANSIBLE_FIXTURE_CONTENT_SUMMARY)

        # Step 4
        sync(self.cfg, collection_remote, repo, mirror=True)
        repo = self.client.get(repo["_href"])
        added_content_summary = get_added_content_summary(repo)
        self.assertGreaterEqual(
            added_content_summary[ANSIBLE_COLLECTION_CONTENT_NAME], ANSIBLE_COLLECTION_FIXTURE_COUNT
        )

        # Step 5
        content_summary = get_content_summary(repo)
        self.assertGreaterEqual(
            content_summary[ANSIBLE_COLLECTION_CONTENT_NAME], ANSIBLE_COLLECTION_FIXTURE_COUNT
        )
        self.assertDictEqual(get_removed_content_summary(
            repo), ANSIBLE_FIXTURE_CONTENT_SUMMARY)

    def test_mirror_sync_with_invalid_requirements(self):
        """
        Sync multiple remotes into the same repo with mirror as `True` with invalid requirement.

        This test targets the following issue: 5250

        * `<https://pulp.plan.io/issues/5250>`_

        This test does the following:

        Try to create a Collection remote with invalid requirement
        """
        collection_remote = self.client.using_handler(api.echo_handler).post(
            ANSIBLE_COLLECTION_REMOTE_PATH,
            gen_ansible_remote(
                url=ANSIBLE_COLLECTION_FIXTURE_URL, requirements_file="INVALID"),
        )

        self.assertEqual(collection_remote.status_code, 400, collection_remote)

    def test_file_decriptors(self):
        """Test whether file descriptors are closed properly.

        This test targets the following issue:
        `Pulp #4073 <https://pulp.plan.io/issues/4073>`_

        Do the following:
        1. Check if 'lsof' is installed. If it is not, skip this test.
        2. Create and sync a repo.
        3. Run the 'lsof' command to verify that files in the
           path ``/var/lib/pulp/`` are closed after the sync.
        4. Assert that issued command returns `0` opened files.
        """
        cli_client = cli.Client(self.cfg, cli.echo_handler)

        # check if 'lsof' is available
        if cli_client.run(("which", "lsof")).returncode != 0:
            raise unittest.SkipTest("lsof package is not present")

        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo["_href"])

        body = gen_ansible_remote(url=ANSIBLE_COLLECTION_TESTING_URL)
        remote = self.client.post(ANSIBLE_COLLECTION_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote["_href"])

        sync(self.cfg, remote, repo)

        cmd = "lsof -t +D {}".format(MEDIA_PATH).split()
        response = cli_client.run(cmd).stdout
        self.assertEqual(len(response), 0, response)
