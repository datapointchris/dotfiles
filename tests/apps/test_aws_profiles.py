"""Tests for aws_profiles.py

The config file is the interesting part: it is hand-edited, assembled by several
tools over years, and AWS's own inheritance rules are not the ones you would
guess. Everything here is a shape a real ~/.aws/config takes.

Run with: pytest tests/apps/test_aws_profiles.py
"""

import json

import aws_profiles
import pytest


@pytest.fixture
def aws_home(tmp_path, monkeypatch):
    """A config and credentials pair, pointed at by the env vars the module reads."""

    def write(config_text: str, credentials_text: str = ''):
        config = tmp_path / 'config'
        credentials = tmp_path / 'credentials'
        config.write_text(config_text)
        credentials.write_text(credentials_text)
        monkeypatch.setattr(aws_profiles, 'CONFIG_PATH', config)
        monkeypatch.setattr(aws_profiles, 'CREDENTIALS_PATH', credentials)
        monkeypatch.setattr(aws_profiles, 'CACHE_PATH', tmp_path / 'cache' / 'identities.json')
        return aws_profiles.profile_settings()

    return write


class TestConfigParsing:
    def test_the_profile_prefix_is_stripped_but_default_is_bare(self, aws_home):
        settings = aws_home('[default]\nregion = us-east-1\n\n[profile work]\nregion = eu-west-1\n')
        assert list(settings) == ['default', 'work']

    def test_a_credentials_only_profile_still_appears(self, aws_home):
        # Role profiles live only in config, so reading either file alone hides
        # half the profiles.
        settings = aws_home('[profile work]\nregion = eu-west-1\n', '[legacy-keys]\naws_access_key_id = AKIA\n')
        assert list(settings) == ['work', 'legacy-keys']

    def test_a_nested_settings_block_does_not_swallow_the_section(self, aws_home):
        # `s3 =` followed by indented keys is valid AWS config and reads as a
        # multi-line value; the keys after it must still be found.
        settings = aws_home(
            '[profile work]\ns3 =\n    max_concurrent_requests = 20\n    max_queue_size = 10000\naccount_label = Acme\nregion = eu-west-1\n'
        )
        assert settings['work']['account_label'] == 'Acme'
        assert settings['work']['region'] == 'eu-west-1'

    def test_a_duplicated_key_is_taken_rather_than_refused(self, aws_home):
        # An ~/.aws/config edited by several tools collects these, and failing to
        # read it at all would be worse than taking the last value.
        settings = aws_home('[profile work]\nregion = us-east-1\nregion = eu-west-1\n')
        assert settings['work']['region'] == 'eu-west-1'

    def test_a_missing_file_is_no_profiles_not_a_crash(self, tmp_path, monkeypatch):
        monkeypatch.setattr(aws_profiles, 'CONFIG_PATH', tmp_path / 'absent')
        monkeypatch.setattr(aws_profiles, 'CREDENTIALS_PATH', tmp_path / 'also-absent')
        assert aws_profiles.profile_settings() == {}


class TestRegionResolution:
    """AWS does not inherit region from [default] for a named profile, so a role
    profile with no region of its own fails every command until one is found.
    """

    CONFIG = (
        '[default]\nregion = us-east-1\n\n'
        '[profile work]\nregion = eu-west-1\n\n'
        '[profile work-admin]\nrole_arn = arn:aws:iam::111:role/Admin\nsource_profile = work\n\n'
        '[profile orphan]\nrole_arn = arn:aws:iam::222:role/ReadOnly\n'
    )

    def test_a_profile_with_its_own_region_uses_it(self, aws_home):
        settings = aws_home(self.CONFIG)
        assert aws_profiles.region_for('work', settings) == 'eu-west-1'

    def test_a_role_profile_inherits_from_the_profile_it_assumes_via(self, aws_home):
        settings = aws_home(self.CONFIG)
        assert aws_profiles.region_for('work-admin', settings) == 'eu-west-1'

    def test_a_role_profile_with_no_source_falls_back_to_default(self, aws_home):
        settings = aws_home(self.CONFIG)
        assert aws_profiles.region_for('orphan', settings) == 'us-east-1'

    def test_no_region_anywhere_is_empty_rather_than_a_guess(self, aws_home):
        settings = aws_home('[profile lonely]\nrole_arn = arn:aws:iam::333:role/X\n')
        assert aws_profiles.region_for('lonely', settings) == ''


class TestIdentity:
    def test_an_assumed_role_arn_reduces_to_the_role_name(self):
        # The session name is per-login noise, so it is dropped.
        assert aws_profiles.short_identity('arn:aws:sts::123:assumed-role/Admin/session-name') == 'role/Admin'

    def test_a_user_arn_is_left_alone(self):
        assert aws_profiles.short_identity('arn:aws:iam::123:user/chris.birch') == 'user/chris.birch'

    def test_an_arn_shape_that_is_neither_still_yields_something(self):
        assert aws_profiles.short_identity('arn:aws:iam::123:root') == 'root'


class TestLabels:
    def test_a_label_covers_every_profile_reaching_that_account(self, aws_home):
        # The label is declared once, on whichever profile happens to carry it,
        # and applies to the account — which is what makes it useful for the
        # several profiles that reach one account by different routes.
        settings = aws_home('[profile work]\naccount_label = Acme Prod\n\n[profile work-admin]\nrole_arn = arn:aws:iam::111:role/Admin\n')
        cache = {'work': {'account': '111', 'identity': 'user/x'}, 'work-admin': {'account': '111', 'identity': 'role/Admin'}}

        rows = aws_profiles.build_rows(list(settings), settings, cache)
        assert [row['label'] for row in rows] == ['Acme Prod', 'Acme Prod']

    def test_an_unresolved_account_gets_no_label(self, aws_home):
        settings = aws_home('[profile work]\naccount_label = Acme\n')
        rows = aws_profiles.build_rows(['work'], settings, {'work': {'account': '?', 'identity': 'unreachable'}})
        assert rows[0]['label'] == ''


class TestMenu:
    def test_columns_are_sized_from_the_widest_value(self, aws_home):
        settings = aws_home('[profile a]\nregion = us-east-1\n\n[profile a-very-long-profile-name]\nregion = us-east-1\n')
        cache = {name: {'account': '111', 'identity': 'user/x'} for name in settings}

        menu = aws_profiles.render_menu(aws_profiles.build_rows(list(settings), settings, cache), '')

        short_row = next(line for line in menu.splitlines() if line.startswith(' 1)'))
        long_row = next(line for line in menu.splitlines() if line.startswith(' 2)'))
        assert short_row.index('111') == long_row.index('111')

    def test_the_label_column_disappears_when_nothing_is_labelled(self, aws_home):
        settings = aws_home('[profile work]\nregion = us-east-1\n')
        menu = aws_profiles.render_menu(aws_profiles.build_rows(['work'], settings, {}), '')
        assert 'LABEL' not in menu

    def test_the_current_profile_is_marked(self, aws_home):
        settings = aws_home('[profile work]\n\n[profile other]\n')
        menu = aws_profiles.render_menu(aws_profiles.build_rows(list(settings), settings, {}), 'other')

        assert any(line.startswith('*2)') for line in menu.splitlines())
        assert any(line.startswith(' 1)') for line in menu.splitlines())

    def test_a_role_profile_says_what_it_is_assumed_through(self, aws_home):
        settings = aws_home('[profile work]\nregion = eu-west-1\n\n[profile admin]\nsource_profile = work\n')
        menu = aws_profiles.render_menu(aws_profiles.build_rows(list(settings), settings, {}), '')
        assert '← assumed via work' in menu


class TestCache:
    def test_a_corrupt_cache_is_ignored_rather_than_fatal(self, tmp_path, monkeypatch):
        cache = tmp_path / 'identities.json'
        cache.write_text('{not json')
        monkeypatch.setattr(aws_profiles, 'CACHE_PATH', cache)
        assert aws_profiles.read_cache() == {}

    def test_the_cache_round_trips(self, tmp_path, monkeypatch):
        cache = tmp_path / 'nested' / 'identities.json'
        monkeypatch.setattr(aws_profiles, 'CACHE_PATH', cache)

        aws_profiles.write_cache({'work': {'account': '111', 'identity': 'user/x'}})

        assert json.loads(cache.read_text()) == {'work': {'account': '111', 'identity': 'user/x'}}
        assert aws_profiles.read_cache()['work']['account'] == '111'
