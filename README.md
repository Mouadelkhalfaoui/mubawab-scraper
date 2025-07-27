# 🏠 Mubawab Scraper - Marrakech

Système de scraping immobilier pour extraire automatiquement les annonces de Mubawab Marrakech.

## 📁 Fichiers du projet

### `main.py` - Serveur API principal
- **FastAPI** avec endpoints REST
- **Scraping multi-threadé** (10 workers simultanés)
- **WebSocket** pour mises à jour temps réel
- **Base SQLite** avec gestion automatique des tables
- **Classes** : `OptimizedMubawabScraper`, `ConnectionManager`

### `index.html` - Interface web
- **Interface responsive** avec design moderne
- **Sélection** des types de propriétés (boutons)
- **Lancement** du scraping avec progression temps réel
- **Affichage** des propriétés avec pagination
- **WebSocket** pour communication avec l'API

### `get_links.py` - Export CSV
- **Extraction** de tous les liens depuis la base SQLite
- **Export complet** : `property_links.csv` (tous types)
- **Export filtré** : `villas_appartements_links.csv`
- **Export récent** : `recent_property_links.csv`
- **Fonctions** : `export_all_property_links_to_csv()`, `export_with_filters()`

## 🗃️ Structure des données

### Tables créées automatiquement

#### Propriétés standard (appartements, villas, maisons, riads, locaux_commerciaux)
```sql
├── id (PRIMARY KEY)
├── titre (TEXT) - Titre de l'annonce
├── prix (TEXT) - Prix affiché  
├── localisation (TEXT) - Quartier/zone
├── surface (TEXT) - Superficie en m²
├── pieces (TEXT) - Nombre de pièces
├── chambres (TEXT) - Nombre de chambres
├── salles_de_bain (TEXT) - Nombre de salles de bain
├── lien (TEXT UNIQUE) - URL Mubawab
├── ville (TEXT) - "Marrakech"
├── image_url (TEXT) - URL de l'image
└── date_scraping (TIMESTAMP) - Date d'extraction
```

#### Terrains (structure simplifiée)
```sql
├── id (PRIMARY KEY)
├── titre (TEXT) - Titre de l'annonce
├── prix (TEXT) - Prix affiché
├── localisation (TEXT) - Quartier/zone  
├── surface (TEXT) - Superficie en m²/hectares
├── lien (TEXT UNIQUE) - URL Mubawab
├── ville (TEXT) - "Marrakech"
├── image_url (TEXT) - URL de l'image
└── date_scraping (TIMESTAMP) - Date d'extraction
```

### Noms des tables
- `appartements` - Appartements
- `villas` - Villas et maisons de luxe
- `maisons` - Maisons  
- `riads` - Riads traditionnels
- `locaux_commerciaux` - Locaux commerciaux
- `terrains` - Terrains

## 🚀 Lancement rapide

```bash
# Installer les dépendances
pip install fastapi uvicorn beautifulsoup4 requests pydantic

# Lancer le serveur
python main.py

# Accéder à l'interface
http://localhost:8000/index.html
```

## 📊 Export des données

```bash
# Exporter tous les liens
python get_links.py

# Fichiers générés :
# - property_links.csv (tous les liens)
# - villas_appartements_links.csv (filtré)  
# - recent_property_links.csv (récent)
```

## 🎯 Workflow typique

1. **Lancer** `python main.py`
2. **Ouvrir** http://localhost:8000/index.html
3. **Sélectionner** type de propriété (ex: appartements)
4. **Cliquer** "Lancer le Scraping"
5. **Suivre** progression WebSocket temps réel
6. **Consulter** résultats dans l'interface
7. **Exporter** avec `python get_links.py`

## 📈 Données collectées

**Exemple d'une propriété :**
```json
{
  "id": 1,
  "titre": "Appartement 3 pièces Hivernage",
  "prix": "1 200 000 DH",
  "localisation": "Hivernage, Marrakech",
  "surface": "120 m²",
  "pieces": "3 Pièces",
  "chambres": "2 Chambres", 
  "salles_de_bain": "2 Salles de bain",
  "lien": "https://www.mubawab.ma/fr/ad/...",
  "ville": "Marrakech",
  "image_url": "https://...",
  "date_scraping": "2025-01-27 14:30:00"
}
```

---
**Base de données** : `mubawab_marrakech_lastversion.db` (SQLite)