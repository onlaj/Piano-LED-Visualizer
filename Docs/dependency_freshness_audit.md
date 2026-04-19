# Audit de dépendances et rapport de fraîcheur

Date d'audit: 2026-04-19

## Périmètre et méthode

Ce rapport couvre uniquement les dépendances directes réellement utilisées par le dépôt:

- dépendances Python déclarées dans `requirements.txt`
- dépendance Node directe déclarée dans `webinterface/package.json`
- bibliothèques front vendoriées effectivement chargées par `webinterface/templates/index.html`

Les versions amont ont été vérifiées sur des sources officielles:

- PyPI pour Python
- npm pour les paquets JavaScript distribués sur npm
- pages upstream officielles quand aucun index npm fiable n'existe pour le script vendorié

Les références runtime ont été confirmées dans le code:

- `webinterface/templates/index.html:20-23` charge `chart.min.js`, `chartjs-adapter-date-fns.bundle.min.js`, `chartjs-plugin-annotation.min.js`, `chartjs-plugin-zoom.js`
- `webinterface/templates/index.html:628-633` charge `alpine.min.js`, `jquery-1.11.1.min.js`, `html-midi-player.js`, `abc2svg-1.js`, `abc2web.js`, `xml2abc.js`
- `webinterface/__init__.py:213-217` gère explicitement l'ancienne et la nouvelle API de chemin de `websockets`
- `webinterface/__init__.py:247` appelle `websockets.serve(...)`
- `webinterface/__init__.py:1,11` et `lib/webinterface_manager.py:5` confirment l'usage de `Flask` et `waitress`

## Dépendances Python

| Dépendance | Version locale / contrainte | Dernière version officielle | Écart | État | Risque | Notes de compatibilité | Source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `RPi.GPIO` | non figé | `0.7.1` | indéterminé au runtime | `à figer / support amont incertain / obsolescence probable` | moyen | Pas de pin: installation non reproductible. Dépendance matérielle Raspberry Pi, à valider sur l'OS et l'archi cible. | [PyPI](https://pypi.org/project/RPi.GPIO/) |
| `webcolors` | `~=25.10.0` | `25.10.0` | aucun | `à jour` | élevé | Montée validée par smoke test sur `hex_to_rgb` et `name_to_rgb`, qui sont les API utilisées par le dépôt. | [PyPI](https://pypi.org/project/webcolors/) |
| `psutil` | `~=7.2.2` | `7.2.2` | aucun | `à jour` | moyen | Montée validée sur les appels `Process()`, `memory_full_info()`, `cpu_percent()` et `virtual_memory()`. | [PyPI](https://pypi.org/project/psutil/) |
| `mido` | `~=1.3.3` | `1.3.3` | aucun | `à jour` | faible | Contrainte alignée sur la dernière version PyPI. | [PyPI](https://pypi.org/project/mido/) |
| `Pillow` | `~=12.2.0` | `12.2.0` | aucun | `à jour` | élevé | Montée validée sur les opérations utilisées par le dépôt: `Image.open/new`, `resize`, et `Image.Resampling.LANCZOS`. | [PyPI](https://pypi.org/project/Pillow/) |
| `python-rtmidi` | non figé | `1.5.8` | indéterminé au runtime | `à figer / support amont incertain / obsolescence probable` | moyen | Pas de pin. Dépendance native, sensible aux wheels disponibles et aux toolchains de build. | [PyPI](https://pypi.org/project/python-rtmidi/) |
| `rpi-ws281x` | `~=5.0.0` | `5.0.0` | aucun | `à jour` | faible | Version alignée. Garder une validation matérielle sur Raspberry Pi avant tout upgrade futur. | [PyPI](https://pypi.org/project/rpi-ws281x/) |
| `spidev` | `~=3.8` | `3.8` | aucun | `à jour` | moyen | Contrainte alignée, mais validation matérielle Raspberry Pi toujours nécessaire. | [PyPI](https://pypi.org/project/spidev/) |
| `numpy` | `~=2.4.4` | `2.4.4` | aucun | `à jour` | élevé | Montée validée sur les primitives utilisées par le dépôt (`asarray`, `abs`, `argmin`, `interp`, `loadtxt`). | [PyPI](https://pypi.org/project/numpy/) |
| `Flask` | `~=3.1.3` | `3.1.3` | aucun | `à jour` | élevé | Montée traitée avec `Werkzeug`; smoke test OK sur l'instanciation `Flask` et `app.json.sort_keys`. | [PyPI](https://pypi.org/project/Flask/) |
| `waitress` | `~=3.0.2` | `3.0.2` | aucun | `à jour` | faible | Contrainte alignée sur la dernière version PyPI. | [PyPI](https://pypi.org/project/waitress/) |
| `websockets` | `~=16.0` | `16.0` | aucun | `à jour` | moyen | Montée validée par smoke test avec `websockets.serve(...)`, connexion réelle, et lecture du chemin via `websocket.request.path`. | [PyPI](https://pypi.org/project/websockets/) |
| `Werkzeug` | `~=3.1.8` | `3.1.8` | aucun | `à jour` | élevé | Montée traitée avec `Flask`; smoke test OK sur `safe_join`. | [PyPI](https://pypi.org/project/Werkzeug/) |

## Dépendance Node directe

| Dépendance | Déclarée | Verrouillée | Dernière version officielle | Écart | État | Risque | Notes de compatibilité | Source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `tailwindcss` | `^4.2.2` | `4.2.2` | `4.2.2` | aucun | `à jour` | élevé | Migration appliquée: CLI v4, `@import \"tailwindcss\"`, `@config`, et safelist convertie en `@source inline(...)`. Build `static/tailwind.css` validé. | [npm](https://www.npmjs.com/package/tailwindcss) |

## Bibliothèques front vendoriées réellement chargées

| Fichier chargé | Version locale confirmée | Dernière version officielle | Écart | État | Risque | Notes | Source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `alpine.min.js` | `2.7.3` | `3.15.11` | saut majeur | `en retard, upgrade majeure` | élevé | Alpine 2 -> 3 comporte des changements de directives et d'initialisation. | [npm](https://www.npmjs.com/package/alpinejs) |
| `jquery-1.11.1.min.js` | `1.11.1` | `4.0.0` | saut majeur | `à figer / support amont incertain / obsolescence probable` | élevé | Version très ancienne. Même si une migration directe vers 4.0 n'est pas réaliste, conserver 1.11.1 augmente le risque de compatibilité navigateur et la dette de maintenance. | [npm](https://www.npmjs.com/package/jquery) |
| `html-midi-player.js` | `1.3.0` | `1.6.0` | mineur | `en retard, upgrade mineure/patch` | moyen | Le bundle local embarque aussi `Tone 14.7.58`; l'upgrade doit être testé côté custom element et lecture MIDI dans le navigateur. | [GitHub releases](https://github.com/cifkao/html-midi-player/releases) |
| `abc2svg-1.js` | `1.20.18` | `1.22.1` | mineur | `à figer / support amont incertain / obsolescence probable` | moyen | npm expose `1.22.1`, mais le paquet y est marqué obsolète et le projet vit surtout hors npm. À mettre à jour seulement si une source upstream stable est retenue pour le vendoring. | [npm](https://www.npmjs.com/package/abc2svg) |
| `abc2web.js` | révision `197` | archive upstream `abcweb_213.zip` | révision plus récente disponible | `à figer / support amont incertain / obsolescence probable` | moyen | Pas de distribution package manager standard; mise à jour manuelle nécessaire depuis le site upstream. | [upstream](https://wim.vree.org/js/) |
| `xml2abc.js` | révision `117` | archive upstream `xml2abc_121.zip` | révision plus récente disponible | `à figer / support amont incertain / obsolescence probable` | moyen | Même contrainte que `abc2web.js`: suivi manuel upstream, sans chaîne de packaging robuste. | [upstream](https://wim.vree.org/js/xml2abc-js_index.html) |
| `chart.min.js` | `4.5.1` | `4.5.1` | aucun | `à jour` | faible | Le socle Chart.js utilisé au runtime est maintenant aligné avec npm; le plugin `chartjs-plugin-zoom.js` chargé est déjà à jour. | [npm](https://www.npmjs.com/package/chart.js) |
| `chartjs-adapter-date-fns.bundle.min.js` | `3.0.0` | `3.0.0` | aucun | `à jour` | faible | Aligné avec la dernière version npm. | [npm](https://www.npmjs.com/package/chartjs-adapter-date-fns) |
| `chartjs-plugin-annotation.min.js` | `3.1.0` | `3.1.0` | aucun | `à jour` | faible | Aligné avec la dernière version npm. | [npm](https://www.npmjs.com/package/chartjs-plugin-annotation) |
| `chartjs-plugin-zoom.js` | `2.2.0` | `2.2.0` | aucun | `à jour` | faible | Version utilisée au runtime déjà à jour. | [npm](https://www.npmjs.com/package/chartjs-plugin-zoom) |

## Artefacts front suspects ou redondants

| Fichier | Version locale | Constat | Impact |
| --- | --- | --- | --- |
| `webinterface/static/js/lib/Chart.bundle.min.js` | `4.5.1` | Duplique fonctionnellement `chart.min.js` et n'est pas référencé par `webinterface/templates/index.html`. | Dette de packaging, poids inutile, risque de confusion lors des mises à jour. |
| `webinterface/static/js/lib/chartjs-plugin-zoom.min.js` | `2.0.1` | Plus ancien que `chartjs-plugin-zoom.js` (`2.2.0`) et non chargé par le template. | Dette de packaging, risque d'erreur humaine si un futur template référence le mauvais fichier. |

## Notes de compatibilité importantes

- `websockets` est déjà traité de façon défensive dans `webinterface/__init__.py:213-217`, avec support de `websocket.request.path` puis fallback vers `websocket.path`. Cela facilite la montée de version, mais ne couvre pas d'autres évolutions d'API de `websockets` 12 -> 16.
- `Flask` et `Werkzeug` doivent être évalués ensemble. Les monter séparément augmenterait le risque de régression dans le serveur web.
- `numpy`, `Pillow`, `webcolors` et `tailwindcss` ont un écart suffisamment important pour justifier une migration dédiée avec tests, pas un simple bump opportuniste.
- Les dépendances Raspberry Pi (`RPi.GPIO`, `rpi-ws281x`, `spidev`) doivent rester prudentes: au-delà de la version Python, la disponibilité des wheels ARM, le kernel, les droits d'accès aux périphériques et le matériel réel peuvent être les vrais points de rupture.
- `html-midi-player.js` est un bundle, pas seulement une façade: la montée de version peut aussi faire évoluer les dépendances embarquées, notamment `Tone`.

## Conclusion priorisée

### Mises à jour simples et recommandées

- Appliquées dans ce dépôt: `mido` `1.3.3`, `waitress` `3.0.2`, `spidev` `3.8`
- Appliquée côté front: `chart.min.js` `4.5.1`
- Validation matérielle Raspberry Pi toujours requise pour `spidev`

### Mises à jour importantes mais risquées

- Appliquées dans ce dépôt: `Flask` `3.1.3`, `Werkzeug` `3.1.8`, `websockets` `16.0`, `psutil` `7.2.2`, `Pillow` `12.2.0`, `numpy` `2.4.4`, `webcolors` `25.10.0`, `tailwindcss` `4.2.2`
- Validation effectuée: `python -m unittest tests.test_usersettings`, `python -m compileall lib webinterface`, smoke tests ciblés sur `Flask`/`Werkzeug`/`websockets`/`psutil`/`Pillow`/`numpy`/`webcolors`, et `npm run build`
- Point d'attention conservé: la migration Tailwind v4 a nécessité une adaptation explicite du pipeline (`@tailwindcss/cli`, `@config`, `@source inline(...)`)

### Composants vendoriés anciens ou potentiellement abandonnés

- `jquery-1.11.1.min.js` est le cas le plus ancien et le plus problématique du front
- `alpine.min.js` reste sur Alpine 2, très en retard
- `abc2svg-1.js`, `abc2web.js` et `xml2abc.js` dépendent d'une chaîne de mise à jour manuelle
- `RPi.GPIO` et `python-rtmidi` ne sont pas figés dans `requirements.txt`, ce qui nuit à la reproductibilité

### Doublons et dette de packaging

- supprimer ou archiver hors runtime `Chart.bundle.min.js`
- supprimer ou archiver hors runtime `chartjs-plugin-zoom.min.js`
- documenter explicitement la source upstream de chaque asset vendorié pour éviter de perdre la traçabilité à la prochaine mise à jour
