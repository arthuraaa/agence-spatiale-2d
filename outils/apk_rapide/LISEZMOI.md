# APK de test rapide (sans SDK Android)

Pour essayer une modification sur ton téléphone en une minute, sans installer le SDK Android ni attendre une construction buildozer. **Pas pour Google Play** : le moteur réutilisé (celui
d'un APK « donneur » libre, python-for-android avec Python 3.10 et pygame 2.1.0) vise une
ancienne version d'Android et n'est pas aligné sur 16 Ko. `outils/verifier_paquet.py` le
refuse d'ailleurs.

```
python outils/apk_rapide/construire.py            # -> bin/agence-spatiale-2d-test.apk
python outils/apk_rapide/verifier.py              # extraction comme sur le téléphone
python outils/apk_rapide/verifier.py --lancer --python310 CHEMIN   # + lancement simulé
```

Il faut Java 17+, pygame, internet au premier lancement (environ 80 Mo mis en cache dans
`cache/`), et un **Python 3.10** (le bytecode doit correspondre au Python du donneur) :
`--python310 C:\Python310\python.exe`, ou `py -3.10` / `python3.10` trouvés tout seuls.
Pour `--lancer`, ce Python 3.10 doit avoir `pygame==2.1.0`.

`cle-test.jks` est une clé de **test** (mot de passe `agence2d`), la même que celle des APK
de test déjà installés : ils se mettent à jour sans perdre la sauvegarde. Ne jamais
l'utiliser pour Google Play.

Attention : si l'appli Google Play garde le même identifiant (`org.agencespatiale.agencespatiale`),
il faudra désinstaller la version de test avant d'installer celle du Play Store (les deux
ne sont pas signées avec la même clé).
