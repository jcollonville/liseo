# Liseo

Liseo est un serveur auto-hébergé, livré en image Docker, qui sert une page web pour Chrome ou Edge. Depuis cette page, on choisit le volume d'une Kobo branchée en USB, on y dépose un prêt de bibliothèque (fichier `.acsm`, PNB / Adobe ADEPT, par exemple Eden Livres) ou un EPUB sans DRM, et le livre est écrit sur la liseuse.

Le `.acsm` n'est pas le livre : c'est un jeton. Le conteneur l'échange, avec un appareil virtuel lié au compte ByteBooks, contre l'**EPUB encore chiffré** et son `META-INF/rights.xml`. La Kobo, autorisée une fois avec Adobe Digital Editions sur le **même** compte, ouvre le livre et applique la date de fin de prêt.

Liseo ne retire jamais cette protection. Les modèles visés sont les Kobo anciennes, qui n'ouvrent pas un `.acsm` toutes seules.

## Contrainte légale

En France, porter atteinte à une mesure technique de protection, ou fournir un moyen conçu pour le faire, est interdit (article L.335-3-1 du code de la propriété intellectuelle, loi DADVSI).

Liseo ne déchiffre pas un EPUB ou un PDF protégé, ne modifie pas `rights.xml`, n'exporte pas de clé et ne propose pas d'activation anonyme. L'image est construite à partir de [libgourou](https://github.com/rledisez/libgourou) v0.8.10, recompilé **sans** :

- l'utilitaire de retrait de DRM ;
- la fonction de retrait dans la bibliothèque ;
- l'export de la clé de licence ;
- l'activation anonyme, que libgourou réserve lui-même aux logiciels de retrait.

L'intégration continue échoue si ces fichiers, symboles ou options réapparaissent dans l'image. Un EPUB récupéré n'est renvoyé au navigateur que s'il contient encore `META-INF/rights.xml` et `META-INF/encryption.xml`.

Ce n'est pas un avis juridique. Le statut d'un client ADEPT qui n'est pas celui d'Adobe, et les conditions d'utilisation ByteBooks ou du PNB, restent à faire valider avant toute diffusion large. L'usage prévu ici est personnel et auto-hébergé.

## Avant la première utilisation

1. Créer ou migrer un identifiant **ByteBooks** (depuis le 23 juin 2026, un Adobe ID ne peut plus activer un nouvel appareil). Garder la même adresse que l'ancien Adobe ID si vous en aviez un.
2. Sur un PC Windows ou Mac, installer Adobe Digital Editions **une fois** : autoriser l'ordinateur avec ce compte, brancher la Kobo, puis autoriser le périphérique. ADE peut ensuite être désinstallé. Chaque Kobo doit l'être avec le même compte que Liseo, sinon la liseuse affichera « Content locked ».
3. Prévoir un fichier `.acsm` que vous acceptez de consommer : la récupération utilise le jeton, qui ne sert qu'une fois.

## Installation

Il faut Docker, puis Chrome ou Edge. Trois étapes :

```bash
cp .env.example .env
# Renseigner LISEO_ADMIN_PASSWORD et LISEO_SECRET_KEY (voir .env.example)
docker compose up -d
```

Ouvrir [http://localhost:8080](http://localhost:8080). `localhost` est un contexte sécurisé : le navigateur peut accéder au dossier de la Kobo. Un serveur sur le réseau local en `http://` simple ne l'est pas ; il faut alors un HTTPS (reverse proxy), ce que ce prototype ne configure pas.

Le volume `liseo-data` contient l'activation de l'appareil virtuel, chiffrée au repos avec `LISEO_SECRET_KEY`. Le mot de passe ByteBooks n'est pas enregistré. Perdre ce volume oblige à activer un nouvel appareil, ce qui consomme un emplacement sur le compte. Ne le supprimez pas à la légère.

L'image publiée `ghcr.io/jcollonville/liseo` n'existe pas encore : `docker compose` construit l'image locale et lui donne ce nom.

## Utilisation

1. Se connecter avec `LISEO_ADMIN_PASSWORD`.
2. Activer le compte ByteBooks. Le mot de passe est transmis à l'outil d'activation par un pseudo-terminal, pas sur la ligne de commande, puis oublié.
3. Brancher la Kobo, choisir son volume (`KOBOeReader`) avec « Sélectionner ma liseuse ». La page affiche le modèle, le firmware et le nombre de livres. S'il manque `.adobe-digital-editions/activation.xml`, la Kobo n'a pas été autorisée.
4. Déposer un `.acsm` ou un EPUB. Le prêt est écrit dans `Liseo/` sur la Kobo, encore chiffré. Un EPUB déjà protégé est copié tel quel. Liseo n'écrit pas dans `.kobo/` ni dans `.adobe-digital-editions/`.
5. Éjecter la liseuse proprement avant de la débrancher.

## Ce que ce prototype ne fait pas encore

- Il n'a pas été essayé sur une vraie Kobo ni avec un vrai serveur Adobe ou Eden. C'est le point à valider en premier : une Kobo ancienne autorisée avec ADE ouvre-t-elle un EPUB récupéré par l'appareil virtuel du même compte ?
- Une Kobo autorisée avant le 23 juin 2026 avec un Adobe ID partage-t-elle la clé de compte d'un appareil activé ensuite avec le ByteBooks ID « migré » ? En cas de doute, réautoriser la Kobo avec ADE et ByteBooks.
- Les tests et l'intégration continue ne contactent pas Adobe, ByteBooks ni Eden. Ces échanges sont simulés.
- Pas de conversion KEPUB, pas de retour anticipé de prêt, pas de liste des échéances, pas de sauvegarde chiffrée exportable, pas de profil HTTPS (Caddy).
- Le choix du volume peut être refusé par le navigateur (racine d'un disque, dossiers cachés). À confirmer sous Windows, macOS et Linux.
- La correspondance code de modèle → nom commercial est incomplète pour quelques Kobo récentes : le code numérique reste affiché.
- Le PNB a annoncé l'abandon de la distribution Adobe. En octobre 2026, les `.acsm` existent encore. Les Kobo ne lisent pas Readium LCP : un fichier LCP est signalé, pas converti.

Le détail et les sources sont dans [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (v0.2).

## Développement

```bash
pip install -r backend/requirements-dev.txt
pytest
```

Les tests couvrent l'analyse d'un `.acsm`, la détection d'une Kobo sur un faux volume, le refus d'un EPUB qui ne serait plus chiffré, et le garde-fou qui cherche les outils de retrait. Pour l'image :

```bash
docker build -t liseo:ci .
python3 scripts/check_drm_guardrail.py --docker-image liseo:ci
```

## Licence

Liseo est sous GPL-3.0-ou-ultérieure. libgourou est sous LGPL-3.0-ou-ultérieure, ses utilitaires sous BSD, uPDFParser sous LGPL-3.0-ou-ultérieure. Les sources patchées de libgourou et celles d'uPDFParser sont dans l'image, sous `/usr/local/src/liseo-third-party`.
