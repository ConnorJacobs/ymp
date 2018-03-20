import logging
import os

import click
import pytest

log = logging.getLogger(__name__)


def test_submit_no_profile(invoker):
    # this should raise a UsageError
    with pytest.raises(click.UsageError):
        invoker.call("submit")


def test_submit_profiles(invoker):
    # try all profiles, but override the cmd to echo
    from ymp.config import icfg
    for profile_name, profile in icfg.cluster.profiles.items():
        if not profile.get('command'):
            continue
        # patch the submit command relative to CWD:
        profile.command = os.sep.join([".", profile.command])
        cmd = profile.command.split()[0]
        with open(cmd, "w") as f:
            f.write('#!/bin/sh\necho "$@">tmpfile\nexec "$@"\n')
            os.chmod(cmd, 0o755)
        if os.path.isdir(icfg.dir.reports):
            os.rmdir(icfg.dir.reports)
        invoker.call("submit",
                     "-p",
                     "--profile", profile_name,
                     "--command", profile.command,
                     icfg.dir.reports)
        assert os.path.isdir(icfg.dir.reports)


def test_show(invoker, saved_tmpdir):
    invoker.call("show")
    res = invoker.call("show", "pairnames")
    assert res.output.strip() == '- R1\n- R2'
    res = invoker.call("show", "pairnames[1]")
    assert res.output.strip() == 'R2'
    res = invoker.call("show", "cluster.profiles.default.drmaa")
    assert res.output.strip() == 'False'

    with open("ymp.yml", "w") as cfg:
        cfg.write("conda:\n  testme: [X1,X2]")
    res = invoker.call("show", "conda.testme")
    assert res.output.strip() == '- X1\n- X2'


def test_stage_list(invoker):
    res = invoker.call("stage", "list")
    assert "\ncheck " in res.output


def test_env_list(invoker):
    res = invoker.call("env", "list")
    assert "\nblast " in res.output


@pytest.mark.parametrize('project', ['toy'], indirect=True)
def test_env_prepare(invoker, project_dir, bin_dir):
    fake_conda = os.path.join(bin_dir, "conda")
    fake_conda_cmd = """\
#!/bin/sh
echo "---\n$0 $@" >> conda_cmd.out
if test "$1" == "--version"; then
  echo conda 4.2
fi
    """
    with open(fake_conda, "w") as f:
        f.write(fake_conda_cmd)
    os.chmod(fake_conda, 0o755)
    res = invoker.call("env", "prepare",
                       "--conda-prefix=.",
                       "toy.trim_bbmap/all")
    assert "bbmap.yml created" in res.output
