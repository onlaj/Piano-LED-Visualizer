# Audit Des Ecarts Du Raspberry Pi

Date: 2026-04-19

## Contexte

Cette note couvre l'audit du dépôt qui tourne sur le Raspberry Pi `pianoledvisualizer.local` par rapport au dépôt local.

Objectifs :
- isoler les écarts réellement pertinents à rapatrier en local
- séparer les changements utiles des fichiers brouillon, backups ou expérimentaux
- garder une trace des points déjà déployés sur le Pi

## Sauvegarde Et Déploiement Deja Effectues Sur Le Pi

Sauvegarde créée sur le Pi avant modification :
- `/home/plv/backups/piano-led-visualizer-20260419-172919.tar.gz`

Changements déjà déployés depuis le dépôt local vers le Pi :
- montée de versions Python et frontend validée localement
- mise à jour des assets Chart.js
- migration Tailwind v4 validée et service relancé

Ces changements ne sont pas des deltas "spécifiques Pi" à rapatrier : ils viennent déjà du dépôt local.

## Synthese

Le dépôt du Pi est très divergent et très sale côté Git. Une grande partie du bruit vient de :
- fichiers suivis modifiés partout dans le dépôt
- fichiers non suivis ajoutés directement sur la machine
- copies de sauvegarde `.bak`
- artefacts manifestement expérimentaux

Après tri, les écarts pertinents se répartissent ainsi :

1. utile et directement réutilisable :
- `scripts/configure_rtpmidi_stability.sh`
- `Docs/rtpmidi_stability.md`

2. utile comme base de travail, mais pas encore intégré :
- `lib/midiport_resolver.py`
- `tests/test_midiport_resolver.py`
- `tests/test_midiports_behavior.py`

3. feature plus lourde, présente en morceaux mais non branchée dans l'application :
- `webinterface/templates/appearance.html`
- `webinterface/static/js/theme.js`

4. à ignorer pour l'instant :
- modules d'optimisation non utilisés
- backups `.bak`
- fichiers dupliqués ou artefacts locaux du Pi

## Changements Pertinents A Porter En Local

### 1. Stabilite RTP MIDI Cote Systeme

Fichiers :
- `scripts/configure_rtpmidi_stability.sh`
- `Docs/rtpmidi_stability.md`

Intérêt :
- ajoute un override systemd pour `rtpmidid`
- force `Restart=always`
- attend `network-online.target`
- désactive l'économie d'énergie Wi-Fi via NetworkManager
- applique aussi `iw dev wlan0 set power_save off` si disponible

Pourquoi c'est pertinent :
- c'est une amélioration opérationnelle claire pour les déploiements Raspberry Pi
- le script est autonome
- la doc explique le comportement attendu sans toucher au cœur applicatif

Recommandation :
- rapatrier ces deux fichiers en local dans un lot séparé "ops / Raspberry Pi"

### 2. Resolver RTP MIDI

Fichiers :
- `lib/midiport_resolver.py`
- `tests/test_midiport_resolver.py`
- `tests/test_midiports_behavior.py`

Ce que fait le resolver :
- normalise les noms de ports ALSA instables
- ignore les faux ports `rtpmidid:Network Export` et `rtpmidid:Announcements`
- gère les variations de suffixes dynamiques `128:3`, `(2)` et `!`
- permet de distinguer "port indisponible" de "session RTP attendue"

Pourquoi l'idée est bonne :
- le besoin métier est réel sur Pi
- les tests capturent de bons cas réels
- la logique évite des bascules vers de faux ports RTP

Pourquoi ce n'est pas prêt à être rapatrié tel quel :
- aucune importation de `lib.midiport_resolver` n'a été trouvée dans le code courant du Pi
- le resolver existe à côté du code principal, mais n'est pas branché dans `lib/midiports.py`
- les tests récupérés supposent des attributs/comportements qui ne sont pas visibles dans le code courant du Pi, par exemple `actual_play_port`

Conclusion :
- à garder comme future base de travail
- à porter en local seulement dans une branche dédiée avec intégration complète

Intégration minimale à prévoir si on le fait :
- brancher le resolver dans `lib/midiports.py`
- exposer le port réellement connecté côté API
- mettre à jour le front pour afficher `actual_play_port` quand il diffère du `play_port` demandé

### 3. Idee UI Associee Au Resolver

Indice intéressant trouvé sur le Pi :
- `webinterface/static/js/ui.js.bak-20260326-appearance-cleanup`

Dans ce backup, le front affiche :
- `response["actual_play_port"] || response["play_port"]`

Le `ui.js` courant du Pi ne le fait pas encore.

Pourquoi c'est utile :
- si on implémente un resolver RTP plus intelligent, le front doit pouvoir montrer le port réellement résolu

Recommandation :
- ne pas reprendre le backup brut
- garder seulement l'idée fonctionnelle pour un futur lot "RTP MIDI robuste"

## Changements Presents Sur Le Pi Mais Pas Assez Matures

### 1. Systeme D'apparence Web

Fichiers repérés :
- `webinterface/templates/appearance.html`
- `webinterface/static/js/theme.js`

Ce qu'ils contiennent :
- une page complète de personnalisation visuelle
- palettes, accent, fond, surface, badges, glow, radius, background mode
- persistance en `localStorage`
- nombreuses clés `web_theme_*`

Pourquoi ce n'est pas prêt à rapatrier :
- aucune inclusion claire de `theme.js` n'a été trouvée dans les templates ou vues courantes
- aucune intégration claire de `appearance.html` dans la navigation ou le routage courant n'a été trouvée
- les seules clés `web_theme_*` observées hors de ces fichiers sont dans `config/settings.xml` sur le Pi, donc dans des réglages runtime locaux

Conclusion :
- feature incomplète ou stationnée sur la machine
- à ne pas rapatrier telle quelle
- si on veut cette feature, il faudra la reprendre comme vrai chantier front

### 2. Modules D'optimisation Non Branches

Fichiers repérés sur le Pi :
- `lib/animation_optimizer.py`
- `lib/animation_utils.py`
- `lib/color_utils.py`
- `lib/colormap_optimizer.py`
- `lib/midi_optimization.py`
- `lib/queue_utils.py`

Constat :
- ces modules n'ont pas montré d'intégration claire dans le code principal
- ils ressemblent à des helpers expérimentaux ou préparatoires

Conclusion :
- ne pas porter en local pour l'instant

## Bruit Ou Artefacts A Ignorer

Fichiers ou familles de fichiers non prioritaires :
- `webinterface/static/js/theme.js.bak-*`
- `webinterface/static/js/ui.js.bak-*`
- `lib/.py`
- fichiers dupliqués à la racine comme `appearance.html`, `theme.js`, `views.py`, `views_api.py`
- fichiers runtime du Pi comme `config/settings.xml`

Raison :
- ils ne décrivent pas un état propre et intégrable du projet

## Decision Recommandee

Lots à faire ensuite côté local :

1. lot recommandé et simple :
- rapatrier `scripts/configure_rtpmidi_stability.sh`
- rapatrier `Docs/rtpmidi_stability.md`

2. lot recommandé mais plus structurant :
- ouvrir un chantier dédié "resolver RTP MIDI"
- repartir de `lib/midiport_resolver.py` et des tests du Pi
- intégrer proprement dans `lib/midiports.py`, l'API et le front

3. lot à repousser :
- système d'apparence web

4. lot à ignorer :
- modules d'optimisation non branchés
- backups et artefacts locaux du Pi

## Execution Du Nettoyage Conservateur

Le nettoyage conservateur a été exécuté sur le Pi le `2026-04-19`.

Sauvegarde créée avant suppression :
- `/home/plv/backups/piano-led-visualizer-20260419-180955.tar.gz`

Supprimé côté Pi :
- feature web lourde non branchée `appearance.html` / `theme.js` et ses backups
- modules expérimentaux non branchés dans `lib/`
- tests non intégrés liés au resolver RTP MIDI
- doublons racine et artefacts de logs/doc non runtime

Conservé volontairement côté Pi :
- `scripts/configure_rtpmidi_stability.sh`
- `Docs/rtpmidi_stability.md`
- `data/` comme donnée runtime potentielle
- les contenus utilisateur non clairement jetables sous `Songs/`
- tous les fichiers suivis modifiés

Vérifications après nettoyage :
- `visualizer.service` actif
- HTTP local `127.0.0.1` en `200`
- WebSocket `ws://127.0.0.1:8765/learning` fonctionnel
- les empreintes SHA-256 des fichiers runtime clés restent identiques entre local et Pi
- `scripts/configure_rtpmidi_stability.sh` passe `bash -n`

Constat :
- le bruit non suivi non branché a été fortement réduit
- le dépôt du Pi reste très sale côté `git status` à cause des nombreux fichiers suivis modifiés, ce qui était attendu

## Gains Et Risques Du Resolver RTP MIDI

Gains potentiels :
- meilleure stabilité face aux noms de ports ALSA dynamiques
- évitement explicite des faux ports `rtpmidid:Network Export` et `rtpmidid:Announcements`
- base de tests utile pour des cas RTP réels
- meilleure UX possible si l'application expose un `actual_play_port`

Risques d'une intégration directe :
- le resolver n'est importé nulle part aujourd'hui
- les tests récupérés supposent une API et des attributs qui n'existent pas encore dans le code courant
- brancher seulement `lib/midiport_resolver.py` sans adapter `lib/midiports.py`, `webinterface/views_api.py` et `webinterface/static/js/ui.js` créerait un état incohérent
- la doc de stabilité RTP mentionne `actual_play_port`, mais ce champ n'est pas encore exposé par l'API actuelle

Conclusion :
- l'idée vaut le coup
- une copie brute depuis le Pi ne vaut pas le coup
- il faut traiter le resolver comme une future amélioration applicative dédiée, pas comme un correctif sans risque

## Etat Final De L'audit

Conclusion pratique :
- oui, il y a des modifications du Pi qui valent la peine d'être notées
- la partie la plus pertinente immédiatement est la stabilisation `rtpmidid` côté système
- le resolver RTP MIDI est intéressant, mais doit être traité comme un vrai développement local, pas comme une copie brute du Pi
- la feature d'apparence web n'est pas suffisamment intégrée pour être reprise telle quelle
