# android/

`manifeste_application.xml` : attributs ajoutés à la balise `<application>` du manifeste
Android (option `android.extra_manifest_application_arguments` de `buildozer.spec`).

- `android:enableOnBackInvokedCallback="false"` : une appli qui vise Android 16 (API 36) ne
  reçoit plus la touche « retour » (retour prédictif activé d'office). Le jeu s'en sert pour
  ouvrir son menu pause : cet attribut garde l'ancien comportement. À vérifier sur un vrai
  téléphone Android 16 après chaque changement de version d'API.
