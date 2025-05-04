# Projet SIE : Système de Gestion des Dons (Flask + Odoo)

## Description du Projet

Ce projet, réalisé dans le cadre d'un cours de Système d'Information d'Entreprise (SIE), implémente une application web basée sur Flask servant d'interface simplifiée pour une ONG gérant des dons de livres et monétaires. L'application Flask s'intègre avec Odoo 16 Community Edition via son API (utilisant la bibliothèque `odoorpc`) pour tirer parti des capacités d'Odoo en tant que système ERP central pour la gestion des stocks, des commandes de vente (pour les donations), des contacts (donateurs) et de la logistique (expéditions).

L'objectif principal était de résoudre le défi concret rencontré par les bénévoles dans les bibliothèques de succursales, qui avaient besoin d'un moyen simple d'enregistrer les dons sans accès direct à Odoo, tout en garantissant que les données d'inventaire critiques (en particulier le stock initial pour les livres donnés) soient mises à jour de manière précise et automatique dans Odoo afin de permettre des processus logistiques en aval fiables.

## Fonctionnalités Clés

* Interface web (Flask) pour l'enregistrement des livres donnés.
* Marquage automatique du statut 'Pending' pour les nouveaux livres dans Odoo via API.
* **Création automatique robuste du stock initial** dans le bon emplacement Odoo après enregistrement du livre (simulation d'une réception `stock.picking`).
* Interface web pour la révision et l'approbation/le rejet des livres (met à jour les tags dans Odoo).
* Affichage des livres approuvés prêts pour expédition.
* Interface web pour créer des expéditions par lot (`stock.picking`) pour les livres approuvés vers les succursales de destination.
* Fonctionnalités pour confirmer, réserver le stock (`action_assign`) et valider les expéditions depuis l'interface Flask.
* Interface web pour l'enregistrement des donateurs/bénévoles (`res.partner`).
* Interface web pour l'enregistrement des donations monétaires (crée une `sale.order` dans Odoo).
* Déploiement conteneurisé utilisant Docker et Docker Compose.

## Stack Technique

* **Framework Web Backend :** Flask (Python 3.10+)
* **Système ERP :** Odoo 16 Community Edition
* **Base de Données :** PostgreSQL 15 (inclus dans le conteneur Odoo)
* **Bibliothèque API Odoo :** `odoorpc`
* **Conteneurisation :** Docker & Docker Compose
* **Bonita BPM Community Edition** pour la modélisation des processus AS-IS / TO-BE

## Configuration et Installation

### Prérequis

* **Docker :** Assurez-vous que Docker Desktop ou Docker Engine est installé sur votre système.  Sinon téléchargez depuis [docker.com](https://www.docker.com/).
* **Docker Compose :** Généralement inclus avec Docker Desktop. Si vous utilisez Docker Engine sur Linux, vous pourriez avoir besoin de l'installer séparément (vérifiez la documentation Docker).

### Configuration

1.  **Cloner le Répertoire Git :**
    ```bash
    git clone [https://github.com/Mihjol-hub/sie-project1-ong.git](https://github.com/Mihjol-hub/sie-project1-ong.git)
    cd sie-project1-ong
    ```

2.  **Variables d'Environnement :** L'application nécessite des détails de connexion pour Odoo et une clé secrète Flask. Ceux-ci sont configurés via des variables d'environnement, principalement définies dans le fichier `docker-compose.yml`.

    * **Pour le Développement (Utilisation des valeurs par défaut de `docker-compose.yml`) :** Le fichier `docker-compose.yml` fourni définit déjà des valeurs par défaut pour le développement local :
        * `ODOO_URL=http://odoo:8069` (Flask se connecte au conteneur Odoo nommé `odoo` sur le port 8069)
        * `ODOO_DB=ong_db` (Nom de base de données par défaut)
        * `ODOO_USER=votre_mail@exemple.com` (Utilisateur Odoo par défaut pour l'API - **Assurez-vous que le nom d'utilisateur existe dans Odoo avec les permissions appropriées !** Voir la section Configuration Odoo ci-dessous.)
        * `ODOO_PASSWORD=simplepassword` (Mot de passe pour l'utilisateur API - **Changez ceci si nécessaire !**)
        * `SECRET_KEY=...` (Une valeur par défaut est fournie, suffisante pour le dev local)
        * Les identifiants PostgreSQL (pour la connexion interne d'Odoo) sont également définis.

    * **Pour la Production/Modification :** Il est fortement recommandé de **NE PAS** stocker d'identifiants sensibles directement dans `docker-compose.yml`. Utilisez l'une de ces méthodes :
        * **Fichier `.env` :** Créez un fichier nommé `.env` à la racine du projet (à côté de `docker-compose.yml`). Définissez-y les variables :
            ```dotenv
            # Fichier .env
            ODOO_URL=http://votre_hote_odoo:8069
            ODOO_DB=votre_base_odoo
            ODOO_USER=votre_utilisateur_api@example.com
            ODOO_PASSWORD=votre_mot_de_passe_api_fort
            SECRET_KEY=votre_tres_forte_cle_secrete_flask_aleatoire
            # Ajoutez les variables PostgreSQL si vous les modifiez dans docker-compose
            # POSTGRES_PASSWORD=votre_mot_de_passe_bd
            ```
            Docker Compose récupérera automatiquement les variables d'un fichier `.env`. Supprimez ou commentez les variables `environment` correspondantes dans `docker-compose.yml` si vous utilisez cette méthode.
        * **Variables d'Environnement Système :** Définissez les variables directement dans l'environnement où vous exécutez `docker compose up`.

3.  **Configuration Odoo (Première Exécution / Si la Base de Données Doit être Initialisée) :**
    * Odoo a besoin d'un "Utilisateur API" (`ODOO_USER`) avec le bon mot de passe (`ODOO_PASSWORD`) et les **permissions** nécessaires. Cet utilisateur doit avoir les droits d'accès généralement associés à :
        * Utilisateur/Manager d'Inventaire (pour lire les emplacements, créer/valider les pickings, lire les produits)
        * Utilisateur de Ventes (pour créer des Commandes de Vente pour les donations)
        * Utilisateur Contacts (pour créer/lire les Partenaires/Donateurs)
        * Potentiellement des droits d'Administration initialement si la création de modèles de données spécifiques est requise.
    * Lors de la *toute première exécution* ou si le volume de données Odoo est vide, l'initialisation de la base de données `ong_db` par Odoo peut prendre un certain temps.
    * *(Optionnel)* Le mot de passe maître Odoo pourrait être nécessaire pour certaines opérations de base de données via l'interface utilisateur Odoo (`/web/database/manager`). Il est commenté dans `docker-compose.yml`.

## Exécution de l'Application

1.  **Construire et Démarrer les Conteneurs :** Ouvrez un terminal à la racine du projet et exécutez :
    ```bash
    docker compose up --build -d
    ```
    * `--build` : Assure que l'image Flask est construite en utilisant le `Dockerfile` actuel.
    * `-d` : Exécute les conteneurs en mode détaché (en arrière-plan).

2.  **Attendre l'Initialisation :** Laissez aux conteneurs (surtout Odoo et la base de données) une minute ou deux pour démarrer complètement, en particulier lors de la première exécution. Vous pouvez surveiller la progression avec `docker compose logs -f odoo`.

3.  **Accéder aux Services :**
    * **Application Web Flask :** Ouvrez votre navigateur et allez à `http://localhost:5001`.
    * **Interface Odoo :** Ouvrez votre navigateur et allez à `http://localhost:8069`. Vous pouvez vous connecter avec les identifiants admin Odoo par défaut (vérifiez la documentation Odoo si vous n'êtes pas sûr, souvent `admin`/`admin` initialement, mais CHANGEZ CECI) ou avec l'utilisateur API configuré (`miguel.romero.3@etu.unige.ch` / `simplepassword` par défaut dans le fichier compose).

## Utilisation et Flux de Travail

1.  **Accéder à l'Application Flask :** Allez à `http://localhost:5001`.
2.  **Enregistrer les Donateurs (Optionnel mais Recommandé) :** Utilisez le lien "Gestion des Donateurs/Bénévoles" -> "Enregistrer un Nouveau Donateur/Bénévole".
3.  **Enregistrer les Livres :** Utilisez "Gestion des Livres Donnés" -> "Enregistrer un Nouveau Livre Donné". Sélectionnez un donateur si disponible. Le livre sera créé dans Odoo, marqué comme "Pending", et **1 unité de stock sera automatiquement ajoutée via une réception `Picking`**.
4.  **Réviser les Livres :** Allez à "Réviser les Livres en Attente". Utilisez les boutons "Approuver" ou "Rejeter". Cela met à jour les tags dans Odoo.
5.  **Préparer l'Expédition :** Allez à "Voir les Livres Approuvés". Sélectionnez un ou plusieurs livres (cases à cocher) et choisissez une succursale de destination. Cliquez sur "Créer l'Expédition de Lot Sélectionnée". Cela crée un `stock.picking` de type 'Branch Shipment' dans Odoo.
6.  **Gérer les Expéditions :** Allez à "Gestion des Expéditions".
    * Trouvez l'expédition nouvellement créée (probablement à l'état 'Draft' ou 'Confirmed').
    * **Confirmer :** Cliquez sur le bouton "Confirmer".
    * **Réserver Stock :** Cliquez sur le bouton "Réserver Stock". Si le stock initial a été ajouté correctement, le statut devrait passer à `assigned` ou `ready`.
    * **Valider :** Cliquez sur "Valider / Détails". Cela vous amène à une page de détails. Entrez la quantité 'Fait' (généralement 1 pour chaque ligne de livre) et cliquez sur "Confirmer les Quantités et Valider l'Expédition". L'expédition devrait maintenant passer à l'état `done` dans Odoo.
7.  **Enregistrer les Donations Monétaires :** Utilisez "Gestion des Donations Monétaires" -> "Enregistrer une Nouvelle Donation Monétaire". Cela crée une Commande de Vente (Sale Order) dans Odoo.
8.  **Voir les Listes :** Utilisez les différents liens "Voir..." pour consulter les listes de livres, de donateurs, de donations et d'expéditions.

## Dépannage / Consultation des Logs

* **Logs de l'Application Flask :** Pour voir les sorties et les erreurs de l'application Flask :
    ```bash
    docker compose logs flask_app
    ```
    Ajoutez `-f` pour suivre les logs en temps réel :
    ```bash
    docker compose logs -f flask_app
    ```
* **Logs du Serveur Odoo :** Pour voir les logs internes, les erreurs et les avertissements d'Odoo :
    ```bash
    docker compose logs odoo
    ```
    Ajoutez `-f` pour suivre les logs en temps réel :
    ```bash
    docker compose logs -f odoo
    ```
* **Logs de la Base de Données (Moins Courant) :**
    ```bash
    docker compose logs odoo_db
    ```

## Arrêter l'Application

Pour arrêter tous les conteneurs en cours d'exécution :
```bash
docker compose down



Modèles de Processus (AS-IS / TO-BE)
Les diagrammes de processus illustrant le flux de travail avant (AS-IS) et après (TO-BE) l'implémentation, créés à l'aide de Bonita BPM Community Edition, se trouvent dans les fichiers suivants :

Fichiers sources Bonita (.proc) : app/diagrams/AS-IS.proc, app/diagrams/TO-BE.proc (Les noms peuvent varier légèrement)
Visualisation facile : Référez-vous aux fichiers image (.png) inclus dans votre soumission ou au Rapport.pdf pour une vue graphique des modèles.
Rapport du Projet
Le rapport complet détaillant l'analyse, la conception, l'implémentation, les défis et les conclusions du projet est disponible dans le fichier :

Rapport.pdf (Situé à la racine de ce dépôt si vous l'y placez pour la soumission)