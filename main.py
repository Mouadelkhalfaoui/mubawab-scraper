from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import sqlite3
import asyncio
import json
from datetime import datetime
import threading
import requests
from bs4 import BeautifulSoup
import re
import math
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import os

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Mubawab Scraper API", version="1.0.0")

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modèles Pydantic
class PropertyBase(BaseModel):
    titre: str
    prix: Optional[str] = "N/A"
    localisation: Optional[str] = "N/A"
    surface: Optional[str] = "N/A"
    lien: str
    ville: str = "Marrakech"
    image_url: Optional[str] = "N/A"

class Property(PropertyBase):
    id: int
    pieces: Optional[str] = "N/A"
    chambres: Optional[str] = "N/A"
    salles_de_bain: Optional[str] = "N/A"
    date_scraping: str

class Terrain(PropertyBase):
    id: int
    date_scraping: str

class ScrapingRequest(BaseModel):
    property_type: str
    max_pages: Optional[int] = None

class ScrapingStatus(BaseModel):
    status: str
    current_page: int
    total_pages: int
    new_properties: int
    total_properties: int
    message: str

# Configuration des types de propriétés
PROPERTY_CONFIGS = {
    'appartements': {
        'base_url': 'https://www.mubawab.ma/fr/ct/marrakech/immobilier-a-vendre',
        'table_name': 'appartements'
    },
    'villas': {
        'base_url': 'https://www.mubawab.ma/fr/st/marrakech/villas-et-maisons-de-luxe-a-vendre',
        'table_name': 'villas'
    },
    'maisons': {
        'base_url': 'https://www.mubawab.ma/fr/st/marrakech/maisons-a-vendre',
        'table_name': 'maisons'
    },
    'riads': {
        'base_url': 'https://www.mubawab.ma/fr/st/marrakech/riads-a-vendre',
        'table_name': 'riads'
    },
    'locaux_commerciaux': {
        'base_url': 'https://www.mubawab.ma/fr/st/marrakech/locaux-a-vendre',
        'table_name': 'locaux_commerciaux'
    },
    'terrains': {
        'base_url': 'https://www.mubawab.ma/fr/st/marrakech/terrains-a-vendre',
        'table_name': 'terrains'
    }
}

# Variable globale pour le chemin de la base de données - NOUVEAU FICHIER
DB_PATH = "mubawab_marrakech_lastversion.db"

def ensure_database_exists():
    """S'assure que la base de données et toutes les tables existent"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Créer toutes les tables nécessaires
        for property_type, config in PROPERTY_CONFIGS.items():
            table_name = config['table_name']
            
            if property_type == 'terrains':
                cursor.execute(f'''
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        titre TEXT NOT NULL,
                        prix TEXT,
                        localisation TEXT,
                        surface TEXT,
                        lien TEXT NOT NULL UNIQUE,
                        ville TEXT NOT NULL,
                        image_url TEXT,
                        date_scraping TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
            else:
                cursor.execute(f'''
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        titre TEXT NOT NULL,
                        prix TEXT,
                        localisation TEXT,
                        surface TEXT,
                        pieces TEXT,
                        chambres TEXT,
                        salles_de_bain TEXT,
                        lien TEXT NOT NULL UNIQUE,
                        ville TEXT NOT NULL,
                        image_url TEXT,
                        date_scraping TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
        
        conn.commit()
        logger.info("Base de données initialisée avec succès")
        
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation de la base de données: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_db_connection():
    """Retourne une connexion à la base de données en s'assurant qu'elle existe"""
    # Vérifier si le fichier DB existe, sinon le créer
    if not os.path.exists(DB_PATH):
        logger.info("Fichier de base de données manquant, création en cours...")
        ensure_database_exists()
    
    return sqlite3.connect(DB_PATH, timeout=30.0)

# Gestion des connexions WebSocket
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except:
                pass

manager = ConnectionManager()

class OptimizedMubawabScraper:
    def __init__(self, property_type: str, websocket_manager: ConnectionManager, max_workers: int = 10):
        self.property_type = property_type
        self.config = PROPERTY_CONFIGS[property_type]
        self.domain = "https://www.mubawab.ma"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
        }
        self.websocket_manager = websocket_manager
        self.max_workers = max_workers
        self.progress_queue = queue.Queue()
        self.total_new_properties = 0
        self.completed_pages = 0
        
        # S'assurer que la base de données existe avant de commencer
        ensure_database_exists()

    def fetch_page(self, url: str) -> Optional[str]:
        """Récupère le contenu HTML d'une page avec retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                time.sleep(0.1 + (attempt * 0.2))
                response = requests.get(url, headers=self.headers, timeout=15)
                response.raise_for_status()
                return response.text
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Erreur finale lors de la requête vers {url}: {e}")
                    return None
                logger.warning(f"Tentative {attempt + 1} échouée pour {url}: {e}")
                time.sleep(1)
        return None

    def get_total_pages(self, html_content: str) -> int:
        """Calcule le nombre total de pages"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            num_results_span = soup.find('span', id='numResults')
            if not num_results_span:
                return 1
            
            total_results_text = num_results_span.text
            total_results = int(re.search(r'\d+', total_results_text).group())

            page_size_input = soup.find('input', id='pageSize')
            if not page_size_input:
                return 1
            
            results_per_page = int(page_size_input['value'])
            total_pages = math.ceil(total_results / results_per_page)
            
            logger.info(f"Total résultats: {total_results}, Pages: {total_pages}")
            return total_pages
        except Exception as e:
            logger.error(f"Erreur lors du calcul du nombre de pages: {e}")
            return 1

    def parse_page(self, html_content: str) -> List[Dict]:
        """Analyse une page et extrait les annonces"""
        if not html_content:
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
        cards = soup.find_all(lambda tag: tag.name in ['li', 'div'] and 'listingBox' in tag.get('class', []))
        
        properties = []
        
        for card in cards:
            title_tag = card.find('h2', class_='listingTit')
            if not title_tag or not title_tag.a:
                continue
            
            try:
                relative_link = title_tag.a.get('href')
                full_link = f"{self.domain}{relative_link}" if relative_link.startswith('/') else relative_link

                # Extraction de l'image
                image_url = 'N/A'
                img_tag = card.find('img')
                if img_tag:
                    image_url = (img_tag.get('src') or img_tag.get('data-src') or 
                               img_tag.get('data-original') or img_tag.get('data-lazy') or 'N/A')
                    if image_url != 'N/A' and image_url.startswith('/'):
                        image_url = f"{self.domain}{image_url}"

                property_data = {
                    'titre': title_tag.a.text.strip(),
                    'lien': full_link,
                    'prix': card.find('span', class_='priceTag').text.strip() if card.find('span', 'priceTag') else 'N/A',
                    'localisation': card.find('span', class_='listingH3').text.strip() if card.find('span', 'listingH3') else 'N/A',
                    'image_url': image_url,
                    'ville': 'Marrakech'
                }

                # Détails spécifiques
                if self.property_type == 'terrains':
                    details = {'surface': 'N/A'}
                else:
                    details = {'surface': 'N/A', 'pieces': 'N/A', 'chambres': 'N/A', 'salles_de_bain': 'N/A'}

                details_container = card.find('div', class_='adDetails')
                if details_container:
                    features = details_container.find_all('div', class_='adDetailFeature')
                    for feature in features:
                        text = feature.text.strip()
                        
                        if self.property_type == 'terrains':
                            if 'm²' in text or 'hectare' in text: 
                                details['surface'] = text
                        else:
                            if 'm²' in text: 
                                details['surface'] = text
                            elif 'Pièce' in text: 
                                details['pieces'] = text
                            elif 'Chambre' in text: 
                                details['chambres'] = text
                            elif 'bain' in text: 
                                details['salles_de_bain'] = text

                property_data.update(details)
                properties.append(property_data)
                
            except Exception as e:
                logger.error(f"Erreur lors de l'analyse d'une propriété: {e}")
                continue

        return properties

    def save_properties(self, properties: List[Dict]) -> int:
        """Sauvegarde les propriétés en base de données avec thread safety"""
        if not properties:
            return 0

        conn = get_db_connection()  # Utiliser la nouvelle fonction
        cursor = conn.cursor()
        new_count = 0

        try:
            conn.execute('BEGIN IMMEDIATE')
            
            for prop in properties:
                try:
                    table_name = self.config['table_name']
                    
                    if self.property_type == 'terrains':
                        sql = f'''
                            INSERT OR IGNORE INTO {table_name} 
                            (titre, prix, localisation, surface, lien, ville, image_url)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        '''
                        data_tuple = (
                            prop.get('titre'), prop.get('prix'), prop.get('localisation'),
                            prop.get('surface'), prop.get('lien'), prop.get('ville'), prop.get('image_url')
                        )
                    else:
                        sql = f'''
                            INSERT OR IGNORE INTO {table_name} 
                            (titre, prix, localisation, surface, pieces, chambres, salles_de_bain, 
                             lien, ville, image_url)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        '''
                        data_tuple = (
                            prop.get('titre'), prop.get('prix'), prop.get('localisation'),
                            prop.get('surface'), prop.get('pieces'), prop.get('chambres'),
                            prop.get('salles_de_bain'), prop.get('lien'), prop.get('ville'), prop.get('image_url')
                        )
                    
                    cursor.execute(sql, data_tuple)
                    if cursor.rowcount > 0:
                        new_count += 1
                        
                except sqlite3.Error as e:
                    logger.error(f"Erreur lors de l'insertion: {e}")
                    continue

            conn.commit()
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur lors de la sauvegarde: {e}")
        finally:
            conn.close()
            
        return new_count

    def scrape_single_page(self, page_num: int, total_pages: int) -> Dict:
        """Scrape une seule page - utilisé par les threads"""
        try:
            url = self.config['base_url'] if page_num == 1 else f"{self.config['base_url']}:p:{page_num}"
            
            html_content = self.fetch_page(url)
            if not html_content:
                return {'page': page_num, 'success': False, 'new_count': 0, 'error': 'Failed to fetch page'}
            
            properties = self.parse_page(html_content)
            new_count = self.save_properties(properties)
            
            self.progress_queue.put({
                'page': page_num,
                'new_count': new_count,
                'success': True
            })
            
            return {
                'page': page_num,
                'success': True,
                'new_count': new_count,
                'properties_found': len(properties)
            }
            
        except Exception as e:
            logger.error(f"Erreur lors du scraping de la page {page_num}: {e}")
            self.progress_queue.put({
                'page': page_num,
                'new_count': 0,
                'success': False,
                'error': str(e)
            })
            return {'page': page_num, 'success': False, 'new_count': 0, 'error': str(e)}

    async def process_progress_updates(self, total_pages: int):
        """Traite les mises à jour de progression en arrière-plan"""
        while self.completed_pages < total_pages:
            try:
                updates_processed = 0
                while not self.progress_queue.empty() and updates_processed < 10:
                    try:
                        update = self.progress_queue.get_nowait()
                        self.completed_pages += 1
                        self.total_new_properties += update['new_count']
                        updates_processed += 1
                        
                        await self.websocket_manager.broadcast({
                            "status": "progress",
                            "message": f"Page {self.completed_pages}/{total_pages} - {update['new_count']} nouvelles propriétés",
                            "current_page": self.completed_pages,
                            "total_pages": total_pages,
                            "new_properties": update['new_count'],
                            "total_properties": self.total_new_properties
                        })
                        
                    except queue.Empty:
                        break
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Erreur lors du traitement des mises à jour: {e}")
                await asyncio.sleep(0.5)

    async def scrape_with_progress(self, max_pages: Optional[int] = None):
        """Lance le scraping multi-threadé avec mise à jour en temps réel"""
        try:
            await self.websocket_manager.broadcast({
                "status": "starting",
                "message": "Initialisation du scraping multi-threadé...",
                "current_page": 0,
                "total_pages": 0,
                "new_properties": 0,
                "total_properties": 0
            })

            first_page_html = self.fetch_page(self.config['base_url'])
            if not first_page_html:
                raise Exception("Impossible de charger la première page")

            total_pages = self.get_total_pages(first_page_html)
            if max_pages:
                total_pages = min(total_pages, max_pages)

            await self.websocket_manager.broadcast({
                "status": "progress",
                "message": f"🚀 Démarrage du scraping parallèle sur {total_pages} pages avec {self.max_workers} threads",
                "current_page": 0,
                "total_pages": total_pages,
                "new_properties": 0,
                "total_properties": 0
            })

            self.total_new_properties = 0
            self.completed_pages = 0
            
            progress_task = asyncio.create_task(self.process_progress_updates(total_pages))

            loop = asyncio.get_event_loop()
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                for page_num in range(1, total_pages + 1):
                    future = loop.run_in_executor(
                        executor, 
                        self.scrape_single_page, 
                        page_num, 
                        total_pages
                    )
                    futures.append(future)
                
                completed_futures = await asyncio.gather(*futures, return_exceptions=True)
                
                successful_pages = 0
                failed_pages = 0
                
                for result in completed_futures:
                    if isinstance(result, Exception):
                        failed_pages += 1
                        logger.error(f"Exception dans une tâche: {result}")
                    elif isinstance(result, dict) and result.get('success'):
                        successful_pages += 1
                    else:
                        failed_pages += 1

            await progress_task
            
            success_message = f"Scraping parallèle terminé! {self.total_new_properties} nouvelles propriétés ajoutées"
            if failed_pages > 0:
                success_message += f" ({successful_pages}/{total_pages} pages réussies)"

            await self.websocket_manager.broadcast({
                "status": "completed",
                "message": success_message,
                "current_page": total_pages,
                "total_pages": total_pages,
                "new_properties": 0,
                "total_properties": self.total_new_properties
            })

            logger.info(f"Scraping terminé: {successful_pages} pages réussies, {failed_pages} échouées, {self.total_new_properties} nouvelles propriétés")
            return self.total_new_properties

        except Exception as e:
            await self.websocket_manager.broadcast({
                "status": "error",
                "message": f"Erreur lors du scraping parallèle: {str(e)}",
                "current_page": 0,
                "total_pages": 0,
                "new_properties": 0,
                "total_properties": 0
            })
            logger.error(f"Erreur critique: {e}")
            raise e

# Initialiser la base de données au démarrage de l'application
@app.on_event("startup")
async def startup_event():
    """Événement de démarrage pour initialiser la base de données"""
    logger.info("Démarrage de l'application - Initialisation de la base de données")
    ensure_database_exists()

# Routes de l'API
@app.get("/")
async def root():
    return {"message": "Mubawab Scraper API - Version Optimisée"}

@app.get("/properties/{property_type}")
async def get_properties(property_type: str, limit: int = 50, offset: int = 0):
    """Récupère les propriétés d'un type donné"""
    if property_type not in PROPERTY_CONFIGS:
        raise HTTPException(status_code=400, detail="Type de propriété invalide")
    
    conn = get_db_connection()  # Utiliser la nouvelle fonction
    cursor = conn.cursor()
    
    table_name = PROPERTY_CONFIGS[property_type]['table_name']
    
    try:
        # Compte total
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        total = cursor.fetchone()[0]
        
        # Récupération des données
        cursor.execute(f"""
            SELECT * FROM {table_name} 
            ORDER BY date_scraping DESC 
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        columns = [description[0] for description in cursor.description]
        properties = []
        
        for row in cursor.fetchall():
            prop_dict = dict(zip(columns, row))
            properties.append(prop_dict)
        
    except sqlite3.OperationalError as e:
        # Si la table n'existe pas, la créer et retourner des résultats vides
        logger.warning(f"Table {table_name} n'existe pas, création en cours...")
        ensure_database_exists()
        total = 0
        properties = []
    
    finally:
        conn.close()
    
    return {
        "properties": properties,
        "total": total,
        "limit": limit,
        "offset": offset
    }

@app.get("/statistics")
async def get_statistics():
    """Récupère les statistiques générales"""
    conn = get_db_connection()  # Utiliser la nouvelle fonction
    cursor = conn.cursor()
    
    stats = {}
    
    for prop_type, config in PROPERTY_CONFIGS.items():
        table_name = config['table_name']
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            stats[prop_type] = count
        except sqlite3.OperationalError:
            # Si la table n'existe pas encore
            stats[prop_type] = 0
    
    conn.close()
    
    return stats

@app.post("/scrape")
async def start_scraping(request: ScrapingRequest):
    """Lance le scraping parallèle pour un type de propriété"""
    if request.property_type not in PROPERTY_CONFIGS:
        raise HTTPException(status_code=400, detail="Type de propriété invalide")
    
    scraper = OptimizedMubawabScraper(request.property_type, manager, max_workers=10)
    
    async def background_scrape():
        try:
            await scraper.scrape_with_progress(request.max_pages)
        except Exception as e:
            logger.error(f"Erreur durante le scraping: {e}")
    
    asyncio.create_task(background_scrape())
    
    return {"message": "Scraping parallèle démarré avec 10 threads", "property_type": request.property_type}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Endpoint WebSocket pour les mises à jour en temps réel"""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Route pour réinitialiser la base de données (utile pour le développement)
@app.post("/reset-database")
async def reset_database():
    """Réinitialise complètement la base de données"""
    try:
        # Supprimer le fichier de base de données s'il existe
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
            logger.info("Ancien fichier de base de données supprimé")
        
        # Recréer la base de données
        ensure_database_exists()
        
        return {"message": "Base de données réinitialisée avec succès"}
    
    except Exception as e:
        logger.error(f"Erreur lors de la réinitialisation: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la réinitialisation: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)