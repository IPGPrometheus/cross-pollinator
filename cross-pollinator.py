#!/usr/bin/env python3
"""
Cross-Pollinator Uploader - Generate Upload Commands

Parses cross-seed database and generates upload.py commands with file paths.
"""
import os
import sqlite3
import sys
import argparse
from collections import defaultdict
from pathlib import Path
from datetime import datetime

# Configuration
CROSS_SEED_DIR = "/cross-seed"
DB_PATH = "/cross-seed/cross-seed.db"

# Comprehensive tracker mapping
TRACKER_MAPPING = {
    'ACM': ['ACM', 'eiga'],
    'AITHER': ['AITHER', 'aither'], 
    'AL': ['AL', 'animelovers'],
    'ANT': ['ANT', 'anthelion'],
    'AR': ['AR', 'alpharatio'],
    'BHD': ['BHD', 'beyond-hd'],
    'BHDTV': ['BHDTV', 'bit-hdtv'],
    'BLU': ['BLU', 'blutopia'],
    'CBR': ['CBR', 'capybarabr'],
    'DP': ['DP', 'darkpeers'],
    'FL': ['FL', 'filelist', 'FileList'],
    'FNP': ['FNP', 'fearnopeer'],
    'FRIKI': ['FRIKI', 'frikibar'],
    'HDB': ['HDB', 'hdbits'],
    'HDT': ['HDT', 'hdts-announce'],
    'HHD': ['HHD', 'homiehelpdesk'],
    'HUNO': ['HUNO', 'hawke'],
    'ITT': ['ITT', 'itatorrents'],
    'LCD': ['LCD', 'locadora'],
    'LST': ['LST', 'lst'],
    'LT': ['LT', 'lat-team'],
    'MTV': ['MTV', 'morethantv'],
    'NBL': ['NBL', 'nebulance'],
    'OE': ['OE', 'onlyencodes'],
    'OTW': ['OTW', 'oldtoons'],
    'PSS': ['PSS', 'privatesilverscreen'],
    'PT': ['PT', 'portugas'],
    'PTER': ['PTER'],
    'PTP': ['PTP'],
    'PTT': ['PTT', 'polishtorrent'],
    'R4E': ['R4E', 'racing4everyone'],
    'RAS': ['RAS', 'rastastugan'],
    'RF': ['RF', 'reelflix'],
    'RTF': ['RTF', 'retroflix'],
    'SAM': ['SAM', 'samaritano'],
    'SN': ['SN', 'swarmazon'],
    'STC': ['STC', 'skipthecommericals'],
    'THR': ['THR', 'torrenthr'],
    'TIK': ['TIK', 'cinematik'],
    'TL': ['TL', 'torrentleech'],
    'TOCA': ['TOCA', 'tocashare'],
    'UHD': ['UHD', 'uhdshare'],
    'ULCX': ['ULCX', 'upload'],
    'UTP': ['UTP'],
    'YOINK': ['YOINK', 'yoinked'],
    'YUS': ['YUS', 'yu-scene']
}

SUCCESS_DECISIONS = ['MATCH', 'MATCH_SIZE_ONLY', 'MATCH_PARTIAL', 'INFO_HASH_ALREADY_EXISTS']

def normalize_tracker_name(raw_name):
    """Normalize tracker names to standard abbreviations."""
    name = raw_name.strip()
    
    if name.startswith('https://'):
        name = name[8:]
    if name.endswith(' (API)'):
        name = name[:-6]
    if name.startswith('FileList-'):
        return 'FL'
    
    for abbrev, variants in TRACKER_MAPPING.items():
        if name in variants or name.lower() in [v.lower() for v in variants]:
            return abbrev
    
    return None

def get_all_configured_trackers():
    """Get all configured trackers from database decisions."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT guid FROM decision WHERE guid IS NOT NULL")
        trackers = set()
        
        for row in cursor.fetchall():
            guid = row[0]
            tracker_name = guid.split('.')[0] if '.' in guid else guid
            normalized = normalize_tracker_name(tracker_name)
            if normalized:
                trackers.add(normalized)
        
        conn.close()
        return sorted(trackers)
        
    except Exception as e:
        print(f"Error getting configured trackers: {e}")
        return []

def get_torrents_with_paths():
    """Get torrents with their file paths and missing trackers."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        all_trackers = get_all_configured_trackers()
        if not all_trackers:
            return []
        
        # Get torrents with paths
        cursor.execute("""
            SELECT name, info_hash, save_path
            FROM client_searchee
            WHERE save_path IS NOT NULL AND save_path != ''
            ORDER BY name
        """)
        
        name_to_info = defaultdict(lambda: {'info_hashes': set(), 'paths': set(), 'found_trackers': set()})
        for row in cursor.fetchall():
            name, info_hash, save_path = row
            name_to_info[name]['info_hashes'].add(info_hash)
            name_to_info[name]['paths'].add(save_path)
        
        # Get latest decisions for each tracker/info_hash
        cursor.execute("""
            SELECT cs.info_hash, d.guid, d.decision, cs.name
            FROM client_searchee cs
            JOIN decision d ON cs.info_hash = d.info_hash
            WHERE d.last_seen = (
                SELECT MAX(d2.last_seen)
                FROM decision d2
                WHERE d2.info_hash = d.info_hash 
                AND d2.guid = d.guid
            )
        """)
        
        # Map decisions to torrents
        for row in cursor.fetchall():
            info_hash, guid, decision, torrent_name = row
            tracker_name = guid.split('.')[0] if '.' in guid else guid
            normalized = normalize_tracker_name(tracker_name)
            if not normalized:
                continue
                
            for name, info in name_to_info.items():
                if info_hash in info['info_hashes']:
                    if decision in SUCCESS_DECISIONS:
                        info['found_trackers'].add(normalized)
                    break
        
        # Build results with missing trackers
        results = []
        for name, info in name_to_info.items():
            missing_trackers = sorted(set(all_trackers) - info['found_trackers'])
            if missing_trackers and info['paths']:
                # Use the first available path
                file_path = list(info['paths'])[0]
                results.append({
                    'name': name,
                    'path': file_path,
                    'missing_trackers': missing_trackers,
                    'found_trackers': sorted(info['found_trackers'])
                })
        
        conn.close()
        return results
        
    except Exception as e:
        print(f"Error getting torrents with paths: {e}")
        return []

def generate_upload_commands(results, output_file=None):
    """Generate upload.py commands and save them to persistent appdata."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    appdata_dir = "/mnt/user/appdata/cross-pollinator"
    os.makedirs(appdata_dir, exist_ok=True)  # make sure the folder exists

    if output_file:
        # Always resolve the file path inside appdata
        filename = os.path.join(appdata_dir, os.path.basename(output_file))
    else:
        filename = os.path.join(appdata_dir, f"upload_commands_{timestamp}.txt")
    
    with open(filename, 'w') as f:
        f.write(f"# Cross-Pollinator Upload Commands - Generated {datetime.now()}\n")
        f.write(f"# Total files needing upload: {len(results)}\n\n")
        
        for item in sorted(results, key=lambda x: x['name'].lower()):
            f.write(f"# {item['name']}\n")
            f.write(f"# Missing from: {', '.join(item['missing_trackers'])}\n")
            f.write(f"# Found on: {', '.join(item['found_trackers']) if item['found_trackers'] else 'None'}\n")
            f.write(f'python3 upload.py "{item["path"]}"\n\n')

    print(f"✅ Upload commands written to: {filename}")
    return filename

def main():
    parser = argparse.ArgumentParser(
        description="Cross-Pollinator Uploader: Generate upload commands"
    )
    parser.add_argument('--run', action='store_true', help='Run upload command generation')
    parser.add_argument('--output', help='Output file for upload commands')
    
    args = parser.parse_args()
    
    if not args.run:
        parser.print_help()
        sys.exit(1)
    
    if not Path(DB_PATH).exists():
        print(f"❌ Database not found: {DB_PATH}")
        sys.exit(1)
    
    print("🔍 Generating upload commands from cross-seed database...")
    results = get_torrents_with_paths()
    
    if not results:
        print("✅ No torrents with paths found needing upload")
        return
    
    print(f"📊 Found {len(results)} torrents with file paths needing upload")
    
    # Generate upload commands
    commands_file = generate_upload_commands(results, args.output)
    print(f"📝 Upload commands written to: {commands_file}")
    
    print("\n✨ Upload command generation complete!")
    print(f"💡 Review {commands_file} before executing upload commands")

if __name__ == "__main__":
    main()