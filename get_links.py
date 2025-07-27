import sqlite3
import csv
import os
from datetime import datetime

def export_all_property_links_to_csv(db_path="mubawab_marrakech_lastversion.db", output_file="property_links.csv"):
    """
    Extracts all property links from the Mubawab SQLite database and exports to CSV
    
    Args:
        db_path (str): Path to the SQLite database
        output_file (str): Output CSV filename
    
    Returns:
        dict: Statistics about the export
    """
    
    # Property configurations from your original code
    PROPERTY_CONFIGS = {
        'appartements': {'table_name': 'appartements'},
        'villas': {'table_name': 'villas'},
        'maisons': {'table_name': 'maisons'},
        'riads': {'table_name': 'riads'},
        'locaux_commerciaux': {'table_name': 'locaux_commerciaux'},
        'terrains': {'table_name': 'terrains'}
    }
    
    # Check if database exists
    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        return None
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Prepare CSV file
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow(['title', 'link', 'category'])
            
            total_exported = 0
            stats = {}
            
            # Process each property type
            for category, config in PROPERTY_CONFIGS.items():
                table_name = config['table_name']
                
                try:
                    # Check if table exists
                    cursor.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' AND name=?
                    """, (table_name,))
                    
                    if not cursor.fetchone():
                        print(f"⚠️  Table '{table_name}' not found, skipping {category}")
                        stats[category] = 0
                        continue
                    
                    # Query all properties with valid links
                    cursor.execute(f"""
                        SELECT titre, lien FROM {table_name}
                        WHERE lien IS NOT NULL 
                        AND lien != 'N/A' 
                        AND lien != ''
                        AND lien LIKE '%mubawab.ma%'
                        ORDER BY date_scraping DESC
                    """)
                    
                    properties = cursor.fetchall()
                    category_count = 0
                    
                    # Write properties to CSV
                    for titre, lien in properties:
                        # Clean title (remove newlines, extra spaces)
                        clean_title = ' '.join(titre.strip().split()) if titre else 'N/A'
                        
                        writer.writerow([clean_title, lien, category])
                        category_count += 1
                        total_exported += 1
                    
                    stats[category] = category_count
                    print(f"✅ {category}: {category_count} properties exported")
                    
                except sqlite3.Error as e:
                    print(f"❌ Error processing {category}: {e}")
                    stats[category] = 0
        
        conn.close()
        
        # Summary
        print(f"\n🎉 Export completed successfully!")
        print(f"📄 File: {output_file}")
        print(f"📊 Total properties exported: {total_exported}")
        print(f"⏰ Export time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return {
            'output_file': output_file,
            'total_exported': total_exported,
            'by_category': stats,
            'export_time': datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ Critical error: {e}")
        return None


def export_with_filters(db_path="mubawab_marrakech_lastversion.db", output_file="filtered_property_links.csv", 
                       categories=None, min_date=None, max_results_per_category=None):
    """
    Export property links with filters
    
    Args:
        db_path (str): Database path
        output_file (str): Output CSV filename
        categories (list): List of categories to export (None = all)
        min_date (str): Minimum scraping date (YYYY-MM-DD format)
        max_results_per_category (int): Maximum results per category
    """
    
    PROPERTY_CONFIGS = {
        'appartements': {'table_name': 'appartements'},
        'villas': {'table_name': 'villas'},
        'maisons': {'table_name': 'maisons'},
        'riads': {'table_name': 'riads'},
        'locaux_commerciaux': {'table_name': 'locaux_commerciaux'},
        'terrains': {'table_name': 'terrains'}
    }
    
    # Filter categories if specified
    if categories:
        PROPERTY_CONFIGS = {k: v for k, v in PROPERTY_CONFIGS.items() if k in categories}
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['title', 'link', 'category', 'price', 'location', 'surface', 'scraping_date'])
            
            total_exported = 0
            
            for category, config in PROPERTY_CONFIGS.items():
                table_name = config['table_name']
                
                # Build query with filters
                query = f"""
                    SELECT titre, lien, prix, localisation, surface, date_scraping 
                    FROM {table_name}
                    WHERE lien IS NOT NULL 
                    AND lien != 'N/A' 
                    AND lien != ''
                    AND lien LIKE '%mubawab.ma%'
                """
                
                params = []
                
                # Add date filter
                if min_date:
                    query += " AND date_scraping >= ?"
                    params.append(min_date)
                
                query += " ORDER BY date_scraping DESC"
                
                # Add limit
                if max_results_per_category:
                    query += " LIMIT ?"
                    params.append(max_results_per_category)
                
                try:
                    cursor.execute(query, params)
                    properties = cursor.fetchall()
                    
                    for titre, lien, prix, localisation, surface, date_scraping in properties:
                        clean_title = ' '.join(titre.strip().split()) if titre else 'N/A'
                        writer.writerow([clean_title, lien, category, prix or 'N/A', 
                                       localisation or 'N/A', surface or 'N/A', date_scraping])
                        total_exported += 1
                    
                    print(f"✅ {category}: {len(properties)} properties exported")
                    
                except sqlite3.Error as e:
                    print(f"❌ Error processing {category}: {e}")
        
        conn.close()
        print(f"\n🎉 Filtered export completed! Total: {total_exported} properties")
        return total_exported
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 0


def check_database_stats(db_path="mubawab_marrakech_lastversion.db"):
    """
    Check database statistics before export
    """
    PROPERTY_CONFIGS = {
        'appartements': {'table_name': 'appartements'},
        'villas': {'table_name': 'villas'},
        'maisons': {'table_name': 'maisons'},
        'riads': {'table_name': 'riads'},
        'locaux_commerciaux': {'table_name': 'locaux_commerciaux'},
        'terrains': {'table_name': 'terrains'}
    }
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("📊 Database Statistics:")
        print("-" * 50)
        
        total_all = 0
        total_with_links = 0
        
        for category, config in PROPERTY_CONFIGS.items():
            table_name = config['table_name']
            
            try:
                # Total count
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                total = cursor.fetchone()[0]
                
                # Count with valid links
                cursor.execute(f"""
                    SELECT COUNT(*) FROM {table_name}
                    WHERE lien IS NOT NULL 
                    AND lien != 'N/A' 
                    AND lien != ''
                    AND lien LIKE '%mubawab.ma%'
                """)
                with_links = cursor.fetchone()[0]
                
                total_all += total
                total_with_links += with_links
                
                percentage = (with_links / total * 100) if total > 0 else 0
                print(f"{category:20}: {with_links:6}/{total:6} ({percentage:5.1f}%)")
                
            except sqlite3.Error as e:
                print(f"{category:20}: Error - {e}")
        
        print("-" * 50)
        print(f"{'TOTAL':20}: {total_with_links:6}/{total_all:6} ({total_with_links/total_all*100 if total_all > 0 else 0:5.1f}%)")
        
        conn.close()
        return total_with_links
        
    except Exception as e:
        print(f"❌ Error checking database: {e}")
        return 0


if __name__ == "__main__":
    # Example usage
    
    print("🔍 Checking database statistics...")
    total_available = check_database_stats()
    
    if total_available > 0:
        print(f"\n📤 Starting export of {total_available} properties...")
        
        # Export all properties
        result = export_all_property_links_to_csv()
        
        if result:
            print(f"\n📈 Export Summary:")
            for category, count in result['by_category'].items():
                print(f"  {category}: {count} properties")
        
        # Example: Export only specific categories
        print(f"\n📤 Exporting only villas and appartements...")
        export_with_filters(
            output_file="villas_appartements_links.csv",
            categories=['villas', 'appartements'],
            max_results_per_category=100
        )
        
        # Example: Export recent properties
        print(f"\n📤 Exporting recent properties (last week)...")
        from datetime import datetime, timedelta
        last_week = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        export_with_filters(
            output_file="recent_property_links.csv",
            min_date=last_week
        )
    
    else:
        print("❌ No properties with valid links found in database!")