# -*- coding: utf-8 -*-
"""La version est cohérente partout : jeu/version.py, buildozer.spec, menu."""
import os, re, sys
RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RACINE)
from jeu.version import __version__, VERSION_CODE


def test_version():
    spec = open(os.path.join(RACINE, "buildozer.spec"), encoding="utf-8").read()
    code = int(re.search(r"(?m)^android\.numeric_version = (\d+)", spec).group(1))
    regex = re.search(r"(?m)^version\.regex = (.*)$", spec).group(1).strip()
    lu = re.search(regex, open(os.path.join(RACINE, "jeu", "version.py"), encoding="utf-8").read()).group(1)
    print("   version %s, versionCode %d (buildozer lit « %s »)" % (__version__, VERSION_CODE, lu))
    assert code == VERSION_CODE, "android.numeric_version doit valoir VERSION_CODE"
    assert lu == __version__ and re.fullmatch(r"\d+\.\d+(\.\d+)?", __version__)
    assert re.search(r"(?m)^android\.api = 36$", spec), "Google Play exige Android 16 (API 36) en 2026"
    assert re.search(r"(?m)^android\.release_artifact = aab$", spec), "Google Play veut un AAB"


if __name__ == "__main__":
    test_version()
    print("--- version : OK")
