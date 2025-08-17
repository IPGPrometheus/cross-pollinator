#!/usr/bin/env python3
"""
Cross-Pollinator - Cross-seed Missing Tracker Analyzer

Analyzes cross-seed database to identify torrents missing from specific trackers.
Focus: Show what needs to be uploaded, not what's already found.
"""

import sqlite3
import sys
import argparse
from collections import defaultdict
from pathlib import Path

# Configuration
CROSS_SEED_DIR = "/cross-seed"
DB_PATH = "/cross-seed/cross-seed.db"

# Comprehensive tracker mapping - only include known trackers
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

# Success decisions that indicate torrent was found
SUCCESS_DECISIONS = ['MATCH', 'MATCH_SIZE_ONLY', 'MATCH_PARTIAL']

def normalize_tracker_name(raw_name):
    """Normalize tracker names to standard abbreviations."""
    name = raw_name.strip()
    
    # Clean prefixes/suffixes
    if name.startswith('https://'):
        name = name[8:]
    if name.endswith(' (API)'):
        name = name[:-6]
    if name.startswith('FileList-'):
        return 'FL'
    
    # Map to abbreviation
    for abbrev, variants in TRACKER_MAPPING.items():
        if name in variants or name.lower() in [v.lower() for v in variants]:
            return abbrev
    
    # Return None for unmapped trackers to filter them out
    return None

def get_all_configured_trackers():
    """Get all configured trackers from database decisions."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get all unique tracker names from decisions
        cursor.execute("SELECT DISTINCT guid FROM decision WHERE guid IS NOT NULL")
        trackers = set()
        
        for row in cursor.fetchall():
            guid = row[0]
            tracker_name = guid.split('.')[0] if '.' in guid else guid
            normalized = normalize_tracker_name(tracker_name)
            if normalized:  # Only include mapped trackers
                trackers.add(normalized)
        
        conn.close()
        return sorted(trackers)
        
    except Exception as e:
        print(f"Error getting configured trackers: {e}")
        return []

def get_latest_torrent_status():
    """
    Get the latest status for each unique torrent (by info_hash).
    Uses the most recent database entry per info_hash to avoid duplicates.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get unique torrents by info_hash with their latest name
        cursor.execute("""
            SELECT cs.info_hash, cs.name
            FROM client_searchee cs
            INNER JOIN (
                SELECT info_hash, MAX(id) as max_id
                FROM client_searchee
                GROUP BY info_hash
            ) latest ON cs.info_hash = latest.info_hash AND cs.id = latest.max_id
            ORDER BY cs.name
        """)
        
        torrents = {}
        for row in cursor.fetchall():
            info_hash, name = row
            torrents[info_hash] = {
                'name': name,
                'found_trackers': set()
            }
        
        # Get all successful matches for these torrents
        cursor.execute("""
            SELECT DISTINCT cs.info_hash, d.guid
            FROM client_searchee cs
            JOIN decision d ON cs.info_hash = d.info_hash
            WHERE d.decision IN (?, ?, ?)
        """, SUCCESS_DECISIONS)
        
        for row in cursor.fetchall():
            info_hash, guid = row
            if info_hash in torrents:
                tracker_name = guid.split('.')[0] if '.' in guid else guid
                normalized = normalize_tracker_name(tracker_name)
                if normalized:  # Only track mapped trackers
                    torrents[info_hash]['found_trackers'].add(normalized)
        
        conn.close()
        return torrents
        
    except Exception as e:
        print(f"Error getting torrent status: {e}")
        return {}

def analyze_missing_trackers():
    """Analyze which trackers each torrent is missing from."""
    all_trackers = get_all_configured_trackers()
    if not all_trackers:
        print("❌ No configured trackers found")
        return [], []
    
    torrents = get_latest_torrent_status()
    if not torrents:
        print("❌ No torrents found in database")
        return [], []
    
    results = []
    for info_hash, torrent_info in torrents.items():
        found_trackers = torrent_info['found_trackers']
        missing_trackers = sorted(set(all_trackers) - found_trackers)
        
        # Only include if missing from at least one tracker
        if missing_trackers:
            results.append({
                'name': torrent_info['name'],
                'info_hash': info_hash,
                'found_trackers': sorted(found_trackers),
                'missing_trackers': missing_trackers
            })
    
    return results, all_trackers

def print_banner():
    """Print application banner."""
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║                        CROSS-POLLINATOR                           ║
║              Cross-seed Missing Tracker Analyzer                  ║
╚═══════════════════════════════════════════════════════════════════╝""")

def print_results(results, all_trackers):
    """Print analysis results - only missing trackers."""
    print_banner()
    
    if not results:
        print("✅ All torrents found on all configured trackers!")
        print(f"🎯 Configured trackers: {', '.join(all_trackers)}")
        return
    
    print(f"📊 Found {len(results)} unique torrents missing from trackers")
    print(f"🎯 Configured trackers: {', '.join(all_trackers)}")
    print("\n🔍 MISSING TRACKER REPORT:")
    print("=" * 100)
    
    for item in sorted(results, key=lambda x: x['name'].lower()):
        missing_list = ", ".join(item['missing_trackers'])
        print(f"{item['name']} | missing from | {missing_list}")
    
    print("=" * 100)
    print(f"📈 Total files needing upload: {len(results)}")

def print_detailed_stats(results, all_trackers):
    """Print detailed statistics."""
    if not results:
        return
        
    print(f"\n📈 UPLOAD STATISTICS")
    print("-" * 50)
    
    tracker_missing_count = defaultdict(int)
    for item in results:
        for tracker in item['missing_trackers']:
            tracker_missing_count[tracker] += 1
    
    print("Files needing upload per tracker:")
    for tracker in sorted(all_trackers):
        count = tracker_missing_count[tracker]
        percentage = (count / len(results) * 100) if results else 0
        status = "🔴" if count > len(results) * 0.5 else "🟡" if count > 0 else "🟢"
        print(f"  {status} {tracker}: {count} files ({percentage:.1f}%)")

def main():
    parser = argparse.ArgumentParser(
        description="Cross-Pollinator: Find torrents missing from trackers"
    )
    parser.add_argument('--run', action='store_true', help='Run analysis')
    parser.add_argument('--stats', action='store_true', help='Show detailed statistics')
    
    args = parser.parse_args()
    
    if not args.run:
        parser.print_help()
        sys.exit(1)
    
    if not Path(DB_PATH).exists():
        print(f"❌ Database not found: {DB_PATH}")
        sys.exit(1)
    
    print("🔍 Analyzing cross-seed database for missing trackers...")
    results, all_trackers = analyze_missing_trackers()
    
    print_results(results, all_trackers)
    
    if args.stats:
        print_detailed_stats(results, all_trackers)
    
    print("\n✨ Analysis complete!")

if __name__ == "__main__":
    main()
