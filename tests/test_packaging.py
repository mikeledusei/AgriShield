"""Install and packaging consistency.

These guard the failure modes that no other test can see, because they happen *before*
any Python runs: a requirements set that cannot resolve, and a documented install or
container path that points at a file that does not exist.

CI installs every component's requirements into one interpreter, so two pins of the same
package are an unsatisfiable set — the whole job dies in seconds with ResolutionImpossible
and reports zero test results. That is cheap to assert and expensive to miss.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = {
    'apps/backend': ROOT / 'apps' / 'backend' / 'requirements.txt',
    'apps/frontend': ROOT / 'apps' / 'frontend' / 'requirements.txt',
    'data_pipeline': ROOT / 'data_pipeline' / 'requirements.txt',
    'ml-models': ROOT / 'ml-models' / 'requirements.txt',
}
PIN = re.compile(r'^([A-Za-z0-9_.\-]+)\s*==\s*([^\s;#]+)')


def pins(path):
    """Pinned versions in a requirements file, keyed by normalised package name."""
    found = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        match = PIN.match(line.split('#', 1)[0].strip())
        if match:
            found[match.group(1).lower()] = match.group(2)
    return found


def test_shared_pins_agree_across_components():
    """A package pinned to two versions across components breaks the combined CI install."""
    seen = {}
    conflicts = []
    for component, path in REQUIREMENTS.items():
        for package, version in pins(path).items():
            if package in seen and seen[package][1] != version:
                conflicts.append(
                    f'{package}: {seen[package][0]} pins {seen[package][1]}, {component} pins {version}'
                )
            seen.setdefault(package, (component, version))
    assert not conflicts, 'conflicting pins make the CI install unsatisfiable: ' + '; '.join(conflicts)


def test_every_requirements_file_exists():
    for component, path in REQUIREMENTS.items():
        assert path.exists(), f'{component} is missing its requirements.txt'
        assert pins(path), f'{component}/requirements.txt has no pinned dependencies'


def test_scikit_learn_matches_the_champion_artifact():
    """The serialized model records the sklearn build that fitted it; a mismatch risks
    unpickling failures or subtly different inference."""
    artifact = ROOT / 'apps/backend/ml_artifacts/lightgbm_agrishield_v1.joblib'
    raw = artifact.read_bytes()
    marker = b'_sklearn_version'
    start = raw.find(marker)
    assert start != -1, 'artifact does not record its scikit-learn version'

    # The pickle stores the version as a short SHORT_BINUNICODE string right after the key.
    tail = raw[start + len(marker):start + len(marker) + 8]
    version = re.search(rb'(\d+\.\d+\.\d+)', tail)
    assert version, 'could not read the artifact scikit-learn version'
    recorded = version.group(1).decode()

    for component in ('apps/backend', 'data_pipeline', 'ml-models'):
        assert pins(REQUIREMENTS[component])['scikit-learn'] == recorded, (
            f'{component} pins scikit-learn {pins(REQUIREMENTS[component])["scikit-learn"]}, '
            f'but the artifact was fitted with {recorded}'
        )


def test_no_deleted_build_files_are_referenced():
    """constraints.txt and requirements-dev.txt were removed deliberately (CHANGELOG).

    A leftover reference is not cosmetic: `docker build` fails at COPY, and the README /
    devcontainer instructions fail on the first install command.
    """
    deleted = ('constraints.txt', 'requirements-dev.txt')
    targets = [
        ROOT / 'README.md',
        ROOT / 'apps' / 'backend' / 'Dockerfile',
        ROOT / 'apps' / 'frontend' / 'Dockerfile',
        ROOT / '.devcontainer' / 'devcontainer.json',
        ROOT / 'scripts' / 'install_venvs.sh',
    ]
    offenders = []
    for path in targets:
        if not path.exists():
            continue
        text = path.read_text(encoding='utf-8')
        for name in deleted:
            # CHANGELOG prose is allowed to mention them; these files must not depend on them.
            if name in text:
                offenders.append(f'{path.relative_to(ROOT)} references {name}')
    assert not offenders, '; '.join(offenders)


def test_dockerfile_copies_only_files_that_exist():
    """Every COPY source in the backend Dockerfile must be a real path (build context is
    the repository root)."""
    dockerfile = ROOT / 'apps' / 'backend' / 'Dockerfile'
    missing = []
    for line in dockerfile.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if not stripped.upper().startswith('COPY '):
            continue
        parts = stripped.split()[1:]
        sources = [part for part in parts[:-1] if not part.startswith('--')]
        for source in sources:
            if not (ROOT / source).exists():
                missing.append(source)
    assert not missing, f'Dockerfile COPY sources do not exist: {missing}'
