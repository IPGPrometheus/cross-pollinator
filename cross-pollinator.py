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
from urllib.parse import urlparse
import re
import time

# Configuration
CROSS_SEED_DIR = "/cross-seed"
DB_PATH = "/cross-seed/cross-seed.db"

# Use environment variable or default to /logs (writable volume)
LOG_DIR = os.environ.get('CROSS_POLLINATOR_LOG_DIR', '/logs')

# Comprehensive tracker mapping - Updated with more trackers and variants
TRACKER_MAPPING = {
    'ACM': ['ACM', 'eiga'],
    'AITHER': ['AITHER', 'aither', 'aither.cc'], 
    'AL': ['AL', 'animelovers'],
    'ANT': ['ANT', 'anthelion', 'anthelion.me'],
    'AR': ['AR', 'alpharatio'],
    'AST': ['AST', 'asiancinema'],
    'ATH': ['ATH', 'asgaard'],
    'AVHD': ['AVHD'],
    'BB': ['BB', 'brokenstones'],
    'BHD': ['BHD', 'beyond-hd', 'beyond-hd.me'],
    'BHDTV': ['BHDTV', 'bit-hdtv'],
    'BLU': ['BLU', 'blutopia', 'blutopia.cc'],
    'BTN': ['BTN', 'broadcasthe.net'],
    'CBR': ['CBR', 'capybarabr'],
    'CRT': ['CRT', 'cathode-ray.tube', 'signal.cathode-ray.tube'],
    'CG': ['CG', 'cinemageddon'],
    'CHD': ['CHD', 'chdbits'],
    'CinemaZ': ['CinemaZ', 'cinemaz'],
    'DT': ['DT', 'desitorrents'],
    'DP': ['DP', 'darkpeers'],
    'EMT': ['EMT', 'empornium'],
    'FNP': ['FNP', 'fearnopeer'],
    'FL': ['FL', 'filelist', 'FileList', 'reactor.filelist.io', 'reactor.thefl.org'],
    'FRIKI': ['FRIKI', 'frikibar'],
    'GGn': ['GGn', 'gazellegames'],
    'GPW': ['GPW', 'great-poisoned-world'],
    'HDB': ['HDB', 'hdbits', 'hdbits.org'],
    'HDC': ['HDC', 'hd-center'],
    'HDF': ['HDF', 'hd-forever'],
    'HDH': ['HDH', 'hdhome'],
    'HDT': ['HDT', 'hdts-announce'],
    'HDU': ['HDU', 'hd-united'],
    'HHD': ['HHD', 'homiehelpdesk'],
    'HPF': ['HPF', 'harrypotterfan'],
    'HUNO': ['HUNO', 'hawke'],
    'iAnon': ['iAnon'],
    'ICE': ['ICE', 'icetorrent'],
    'IPT': ['IPT', 'iptorrents'],
    'ITT': ['ITT', 'itatorrents'],
    'JPopsuki': ['JPopsuki'],
    'KG': ['KG', 'karagarga'],
    'LCD': ['LCD', 'locadora'],
    'LST': ['LST', 'lst'],
    'LT': ['LT', 'lat-team'],
    'MAM': ['MAM', 'myanonamouse'],
    'ME': ['ME', 'milkie'],
    'MTV': ['MTV', 'morethantv', 'morethantv.me'],
    'MTeam': ['MTeam'],
    'NBL': ['NBL', 'nebulance'],
    'NC': ['NC', 'norbits'],
    'NM': ['NM', 'nostream'],
    'OE': ['OE', 'onlyencodes'],
    'OPS': ['OPS', 'orpheus'],
    'OTW': ['OTW', 'oldtoons'],
    'PB': ['PB', 'privatebits'],
    'PHD': ['PHD', 'privatehd'],
    'PirateTheNet': ['PirateTheNet', 'piratethenet'],
    'PSS': ['PSS', 'privatesilverscreen'],
    'PT': ['PT', 'portugas'],
    'PTER': ['PTER'],
    'PTP': ['PTP', 'passthepopcorn.me'],
    'PTT': ['PTT', 'polishtorrent'],
    'R4E': ['R4E', 'racing4everyone'],
    'RAS': ['RAS', 'rastastugan'],
    'RED': ['RED', 'redacted'],
    'RF': ['RF', 'reelflix'],
    'RTF': ['RTF', 'retroflix'],
    'SAM': ['SAM', 'samaritano'],
    'SC': ['SC', 'scenetime'],
    'SN': ['SN', 'swarmazon'],
    'SPD': ['SPD', 'speedapp'],
    'STC': ['STC', 'skipthecommericals'],
    'THC': ['THC', 'thehorrorcult'],
    'THR': ['THR', 'torrenthr'],
    'TIK': ['TIK', 'cinematik'],
    'TL': ['TL', 'torrentleech', 'tleechreload.org', 'torrentleech.org'],
    'TOCA': ['TOCA', 'tocashare'],
    'TS': ['TS', 'torrentseeds'],
    'TSP': ['TSP', 'thesceneplace'],
    'TVC': ['TVC', 'tvchaosuk'],
    'TVV': ['TVV', 'tv-vault'],
    'UHD': ['UHD', 'uhdshare'],
    'ULCX': ['ULCX', 'upload'],
    'UTP': ['UTP'],
    'WCD': ['WCD', 'whatcd'],
    'x264': ['x264'],
    'XS': ['XS', 'xspeeds'],
    'YOINK': ['YOINK', 'yoinked'],
    'YUS': ['YUS', 'yu-scene']
}

# Anime-specific trackers that should only be considered for anime content
ANIME_TRACKERS = {'AL', 'ACM'}

# General movie/TV trackers that should be excluded from anime content
GENERAL_TRACKERS = {'PTP', 'HDB', 'BLU', 'BHD', 'AITHER', 'ANT', 'MTV', 'FL', 'TL', 'BTN', 'PHD'}

SUCCESS_DECISIONS = ['MATCH', 'MATCH_SIZE_ONLY', 'MATCH_PARTIAL', 'INFO_HASH_ALREADY_EXISTS', 'MATCH_TORRENT']

def print_progress_bar(current, total, start_time, prefix="Progress", length=50):
    """Print a progress bar with estimated time remaining."""
    if total == 0:
        return
    
    percent = current / total
    filled_length = int(length * percent)
    bar = '█' * filled_length + '-' * (length - filled_length)
    
    # Calculate time estimates
    elapsed_time = time.time() - start_time
    if current > 0:
        avg_time_per_item = elapsed_time / current
        remaining_items = total - current
        eta_seconds = avg_time_per_item * remaining_items
        eta_str = f"ETA: {int(eta_seconds//60):02d}:{int(eta_seconds%60):02d}"
    else:
        eta_str = "ETA: --:--"
    
    print(f'\r{prefix}: |{bar}| {current}/{total} ({percent:.1%}) {eta_str}', end='', flush=True)

def is_video_file(filename):
    """Check if filename has a video file extension."""
    video_extensions = {
        '.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v',
        '.mpg', '.mpeg', '.3gp', '.3g2', '.asf', '.rm', '.rmvb', '.vob',
        '.ts', '.mts', '.m2ts', '.divx', '.xvid', '.f4v', '.ogv'
    }
    return Path(filename).suffix.lower() in video_extensions

def is_anime_content(filename):
    """Detect if content is likely anime based on filename patterns."""
    filename_lower = filename.lower()
    
    # Common anime patterns
    anime_indicators = [
        # Episode patterns
        r's\d{2}e\d{2}',  # S01E01 format
        r'ep\d+',         # Episode number
        r'episode\s*\d+', # Episode word + number
        
        # Japanese/anime specific terms
        'anime', 'manga', 'ova', 'ona', 'special', 'omake',
        
        # Common anime groups/tags
        'horriblesubs', 'subsplease', 'erai-raws', 'commie',
        
        # Language indicators
        'japanese', 'jpn', 'subbed', 'dubbed'
    ]
    
    for pattern in anime_indicators:
        if re.search(pattern, filename_lower):
            return True
    
    # Check for common anime series patterns (often have Japanese romanized names)
    # This is basic - could be expanded with a more comprehensive approach
    return False

def normalize_tracker_name(raw_name):
    """Normalize tracker names to standard abbreviations using TRACKER_MAPPING."""
    name = raw_name.strip()
    original_name = name

    if name.startswith('Filelist-'):
        return 'FL'

    host = name.lower()
    if name.startswith('http'):
        try:
            parsed = urlparse(name)
            host = parsed.netloc.lower()
        except Exception:
            pass

    # Strip leading www.
    if host.startswith("www."):
        host = host[4:]

    # Match against TRACKER_MAPPING
    for abbrev, variants in TRACKER_MAPPING.items():
        for variant in variants:
            v = variant.lower()
            if v in host or host in v:
                return abbrev

    print(f"🔍 DEBUG: Could not normalize tracker '{original_name}' -> '{host}'")
    return None

def get_active_trackers():
    """Get trackers that you actually have successful uploads/downloads on."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get trackers where you have successful matches (indicating you're active on them)
        cursor.execute("""
            SELECT DISTINCT value
            FROM client_searchee, json_each(client_searchee.trackers)
            WHERE value IS NOT NULL AND value != ''
        """)
        
        active_trackers = set()
        for row in cursor.fetchall():
            guid = row[0]
            tracker_name = guid.split('.')[0] if '.' in guid else guid
            normalized = normalize_tracker_name(tracker_name)
            if normalized:
                active_trackers.add(normalized)
        
        conn.close()
        return sorted(active_trackers)
        
    except Exception as e:
        print(f"Error getting active trackers: {e}")
        return []

def get_all_configured_trackers():
    """Get all configured trackers from client_searchee.trackers (JSON)."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT value
            FROM client_searchee, json_each(client_searchee.trackers)
            WHERE value IS NOT NULL AND value != ''
        """)
        
        trackers = set()
        for row in cursor.fetchall():
            tracker_url = row[0]
            normalized = normalize_tracker_name(tracker_url)
            if normalized:
                trackers.add(normalized)
        
        conn.close()
        return sorted(trackers)

    except Exception as e:
        print(f"Error getting configured trackers: {e}")
        return []

def filter_relevant_trackers(all_trackers, filename, active_trackers):
    """Filter trackers based on content type and user's active trackers."""
    is_anime = is_anime_content(filename)
    
    # Only consider trackers you're actually active on
    relevant_trackers = set(all_trackers) & set(active_trackers)
    
    if is_anime:
        # For anime, include anime trackers and exclude general movie/TV trackers
        return sorted(relevant_trackers & (ANIME_TRACKERS | (relevant_trackers - GENERAL_TRACKERS)))
    else:
        # For non-anime, exclude anime-specific trackers
        return sorted(relevant_trackers - ANIME_TRACKERS)

def get_torrents_with_paths():
    """Get torrents with their file paths and missing trackers."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # First, let's check what columns exist in client_searchee
        cursor.execute("PRAGMA table_info(client_searchee)")
        columns = cursor.fetchall()
        print("🔍 Available columns in client_searchee:")
        for col in columns:
            print(f"   {col[1]} ({col[2]})")
        
        # Check if there's a tracker column
        column_names = [col[1] for col in columns]
        has_tracker_column = 'tracker' in column_names
        
        print("🔍 Getting configured trackers...")
        all_trackers = get_all_configured_trackers()
        active_trackers = get_active_trackers()
        
        if not all_trackers:
            return []
        
        print("📊 Analyzing torrents and their tracker status...")
        start_time = time.time()
        
        # Get torrents with paths
        cursor.execute("""
            SELECT name, info_hash, save_path
            FROM client_searchee
            WHERE save_path IS NOT NULL AND save_path != ''
            ORDER BY name
        """)
        
        torrent_rows = cursor.fetchall()
        total_torrents = len(torrent_rows)
        
        if total_torrents == 0:
            print("No torrents with paths found in database")
            return []
        
        name_to_info = defaultdict(lambda: {'info_hashes': set(), 'paths': set(), 'found_trackers': set()})
        info_hash_to_name = {}  # Map info_hash to torrent name for faster lookup
        
        # Process torrents with progress bar
        for i, row in enumerate(torrent_rows):
            print_progress_bar(i + 1, total_torrents, start_time, "Processing torrents")
            name, info_hash, save_path = row
            name_to_info[name]['info_hashes'].add(info_hash)
            name_to_info[name]['paths'].add(save_path)
            info_hash_to_name[info_hash] = name
        
        print()  # New line after progress bar
        
        if has_tracker_column:
            # Cross-reference successful decisions with client_searchee tracker info
            print("🔄 Cross-referencing successful decisions with tracker info...")
            cursor.execute("""
                SELECT DISTINCT d.info_hash, cs.tracker
                FROM decision d
                JOIN client_searchee cs ON d.info_hash = cs.info_hash
                WHERE d.decision IN ('MATCH', 'MATCH_SIZE_ONLY', 'MATCH_PARTIAL', 'INFO_HASH_ALREADY_EXISTS')
                AND cs.tracker IS NOT NULL
                AND cs.tracker != ''
            """)
            
            cross_ref_rows = cursor.fetchall()
            total_cross_refs = len(cross_ref_rows)
            
            # Process cross-referenced data with progress bar
            cross_ref_start = time.time()
            debug_tracker_matches = defaultdict(int)  # Debug: count successful tracker matches
            unmatched_domains = set()  # Track unmatched domains for debugging
            
            for i, row in enumerate(cross_ref_rows):
                if i % 100 == 0 or i == total_cross_refs - 1:  # Update every 100 items or at the end
                    print_progress_bar(i + 1, total_cross_refs, cross_ref_start, "Cross-referencing trackers")
                
                info_hash, tracker_url = row
                
                # Look up torrent name by info_hash
                if info_hash in info_hash_to_name:
                    torrent_name = info_hash_to_name[info_hash]
                    
                    # Extract domain from tracker URL
                    if tracker_url.startswith('http'):
                        try:
                            from urllib.parse import urlparse
                            parsed = urlparse(tracker_url)
                            domain = parsed.netloc.lower()
                            
                            # Find matching tracker in TRACKER_MAPPING
                            found_tracker = None
                            for abbrev, variants in TRACKER_MAPPING.items():
                                # Check if domain matches any variant (case-insensitive)
                                for variant in variants:
                                    if variant.lower() in domain or domain in variant.lower():
                                        found_tracker = abbrev
                                        break
                                if found_tracker:
                                    break
                            
                            if found_tracker:
                                name_to_info[torrent_name]['found_trackers'].add(found_tracker)
                                debug_tracker_matches[found_tracker] += 1
                            else:
                                # Track unmatched domains for debugging
                                unmatched_domains.add(domain)
                                
                        except Exception as e:
                            print(f"Error parsing tracker URL {tracker_url}: {e}")
                            continue
                    else:
                        # Non-URL tracker name - try direct mapping
                        found_tracker = None
                        for abbrev, variants in TRACKER_MAPPING.items():
                            if tracker_url in variants or tracker_url.lower() in [v.lower() for v in variants]:
                                found_tracker = abbrev
                                break
                        
                        if found_tracker:
                            name_to_info[torrent_name]['found_trackers'].add(found_tracker)
                            debug_tracker_matches[found_tracker] += 1
                        else:
                            unmatched_domains.add(tracker_url)
            
            print()  # New line after progress bar
            
            # Debug output: show tracker match counts
            if debug_tracker_matches:
                print("🔍 Debug - Tracker matches from cross-reference:")
                for tracker, count in sorted(debug_tracker_matches.items()):
                    print(f"   {tracker}: {count} matches")
            else:
                print("⚠️  Debug - No tracker matches found from cross-reference!")
            
            # Show unmatched domains for debugging (limit to first 10)
            if unmatched_domains:
                print(f"🔍 Debug - Unmatched domains/trackers (showing first 10):")
                for domain in sorted(list(unmatched_domains)[:10]):
                    print(f"   {domain}")
        else:
            # No tracker column, fall back to GUID method
            print("⚠️  No tracker column found in client_searchee, falling back to GUID analysis...")
            
            # Get all decisions and extract tracker info from GUIDs
            cursor.execute("""
                SELECT info_hash, guid, decision, last_seen
                FROM decision
                WHERE guid IS NOT NULL
                AND decision IN ('MATCH', 'MATCH_SIZE_ONLY', 'MATCH_PARTIAL', 'INFO_HASH_ALREADY_EXISTS')
                ORDER BY info_hash, guid, last_seen DESC
            """)
            
            decision_rows = cursor.fetchall()
            total_decisions = len(decision_rows)
            
            # Process decisions with progress bar - keep only latest decision per info_hash/guid pair
            decision_start = time.time()
            processed_pairs = set()  # Track processed (info_hash, guid) pairs
            debug_tracker_matches = defaultdict(int)  # Debug: count successful tracker matches
            
            for i, row in enumerate(decision_rows):
                if i % 100 == 0 or i == total_decisions - 1:  # Update every 100 decisions or at the end
                    print_progress_bar(i + 1, total_decisions, decision_start, "Processing decisions")
                
                info_hash, guid, decision, last_seen = row
                pair_key = (info_hash, guid)
                
                # Skip if we've already processed this info_hash/tracker combination (keeps latest due to ORDER BY)
                if pair_key in processed_pairs:
                    continue
                processed_pairs.add(pair_key)
                
                # Extract tracker name from GUID - simplified approach
                normalized_tracker = None
                
                if guid.startswith('FileList-'):
                    normalized_tracker = 'FL'
                elif guid.startswith('https://'):
                    # Remove https:// and take the domain
                    try:
                        domain = guid[8:].split('/')[0].lower()
                        
                        # Direct domain mapping
                        domain_mapping = {
                            'hawke.uno': 'HUNO',
                            'www.torrentleech.org': 'TL',
                            'torrentleech.org': 'TL',
                            'tleechreload.org': 'TL',
                            'seedpool.org': 'SPD',
                            'oldtoons.world': 'OTW',
                            'lst.gg': 'LST',
                            'onlyencodes.cc': 'OE',
                            'aither.cc': 'AITHER',
                            'www.cathode-ray.tube': 'CRT',
                            'cathode-ray.tube': 'CRT',
                            'signal.cathode-ray.tube': 'CRT',
                            'blutopia.cc': 'BLU',
                            'beyond-hd.me': 'BHD',
                            'anthelion.me': 'ANT',
                            'hdbits.org': 'HDB',
                            'passthepopcorn.me': 'PTP',
                            'morethantv.me': 'MTV',
                            'filelist.io': 'FL',
                            'reactor.filelist.io': 'FL',
                            'reactor.thefl.org': 'FL'
                        }
                        
                        normalized_tracker = domain_mapping.get(domain)
                        
                        # Handle incomplete URLs like https://www or https://seedpool
                        if not normalized_tracker and '.' not in domain:
                            if domain == 'www':
                                normalized_tracker = 'TL'  # Assuming www is torrentleech
                            elif domain == 'seedpool':
                                normalized_tracker = 'SPD'
                            elif domain == 'lst':
                                normalized_tracker = 'LST'
                            elif domain == 'oldtoons':
                                normalized_tracker = 'OTW'
                        
                    except Exception:
                        pass
                else:
                    # Try existing normalization for non-URLs
                    normalized_tracker = normalize_tracker_name(guid)
                
                if normalized_tracker and info_hash in info_hash_to_name:
                    torrent_name = info_hash_to_name[info_hash]
                    name_to_info[torrent_name]['found_trackers'].add(normalized_tracker)
                    debug_tracker_matches[normalized_tracker] += 1
            
            print()  # New line after progress bar
            
            # Debug output: show tracker match counts
            if debug_tracker_matches:
                print("🔍 Debug - Tracker matches from GUID analysis:")
                for tracker, count in sorted(debug_tracker_matches.items()):
                    print(f"   {tracker}: {count} matches")
            else:
                print("⚠️  Debug - No tracker matches found from GUID analysis!")
        
        print()  # New line after debug output
        
        print("🔄 Grouping content and detecting duplicates...")
        # Group by normalized content name to detect duplicates
        content_groups = defaultdict(list)
        video_files = 0
        
        for name, info in name_to_info.items():
            if is_video_file(name):
                video_files += 1
                normalized_name = normalize_content_name(name)
                content_groups[normalized_name].append((name, info))
        
        print(f"📹 Found {video_files} video files to analyze")
        
        # Build results with missing trackers
        results = []
        processed_content = set()
        analysis_start = time.time()
        total_content_groups = len(content_groups)
        
        for i, (normalized_name, items) in enumerate(content_groups.items()):
            print_progress_bar(i + 1, total_content_groups, analysis_start, "Analyzing content")
            
            if normalized_name in processed_content:
                continue
            
            # For duplicate content, merge the found_trackers and use the first item
            if len(items) > 1:
                # Merge found trackers from all variants
                merged_found_trackers = set()
                primary_item = items[0]  # Use first item as primary
                
                for name, info in items:
                    merged_found_trackers.update(info['found_trackers'])
                
                # Update primary item with merged trackers
                primary_item[1]['found_trackers'] = merged_found_trackers
                name, info = primary_item
            else:
                name, info = items[0]
            
            # Filter trackers based on content type and active trackers
            relevant_trackers = filter_relevant_trackers(all_trackers, name, active_trackers)
            missing_trackers = sorted(set(relevant_trackers) - info['found_trackers'])
            
            if missing_trackers and info['paths']:
                # Use the first available path
                file_path = list(info['paths'])[0]
                results.append({
                    'name': name,
                    'path': file_path,
                    'missing_trackers': missing_trackers,
                    'found_trackers': sorted(info['found_trackers'] & set(relevant_trackers)),
                    'normalized_name': normalized_name,
                    'duplicates': [item[0] for item in items] if len(items) > 1 else None
                })
            
            processed_content.add(normalized_name)
        
        print()  # New line after progress bar
        conn.close()
        return results
        
    except Exception as e:
        print(f"Error getting torrents with paths: {e}")
        return []

def generate_upload_commands(results, output_file=None, clean_output=False):
    """Generate upload.py commands and save them to persistent appdata."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Ensure LOG_DIR is a Path object for consistency
    appdata_dir = Path(LOG_DIR)
    appdata_dir.mkdir(parents=True, exist_ok=True)  # Create directory if it doesn't exist

    if output_file:
        # Always resolve the file path inside appdata
        filename = appdata_dir / Path(output_file).name
    else:
        filename = appdata_dir / f"upload_commands_{timestamp}.txt"
    
    print("📝 Generating upload commands...")
    start_time = time.time()
    
    with open(filename, 'w') as f:
        if not clean_output:
            f.write(f"# UAhelper: Generated {datetime.now()}\n")
            f.write(f"# Total files needing upload: {len(results)}\n\n")
        
        for i, item in enumerate(sorted(results, key=lambda x: x['name'].lower())):
            print_progress_bar(i + 1, len(results), start_time, "Writing commands")
            
            if not clean_output:
                f.write(f"# {item['name']}\n")
                if item.get('duplicates'):
                    f.write(f"# Duplicates: {', '.join(item['duplicates'])}\n")
                f.write(f"# Missing from: {', '.join(item['missing_trackers'])}\n")
                f.write(f"# Found on: {', '.join(item['found_trackers']) if item['found_trackers'] else 'None'}\n")
            
            # Construct the full file path by combining directory and filename
            base_path = Path(item["path"])
            torrent_name = item["name"]
            
            # Construct full path: directory + torrent name
            full_file_path = base_path / torrent_name
            
            # Create the tracker list parameter - only include missing trackers
            tracker_list = ','.join(item['missing_trackers'])
            
            f.write(f'python3 upload.py "{full_file_path}" --trackers {tracker_list}\n')
            if not clean_output:
                f.write('\n')
    
    print()  # New line after progress bar
    print(f"✅ Upload commands written to: {filename}")
    return filename

def debug_database_content(limit=10):
    """Debug function to inspect database content and write to file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    appdata_dir = Path(LOG_DIR)
    appdata_dir.mkdir(parents=True, exist_ok=True)
    debug_file = appdata_dir / f"debug_output_{timestamp}.txt"
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        with open(debug_file, 'w') as f:
            f.write("🔍 DEBUG: Database Analysis\n")
            f.write("=" * 50 + "\n")
            
            # Check client_searchee table
            cursor.execute("SELECT COUNT(*) FROM client_searchee")
            searchee_count = cursor.fetchone()[0]
            f.write(f"Total client_searchee records: {searchee_count}\n")
            
            cursor.execute("SELECT COUNT(*) FROM client_searchee WHERE save_path IS NOT NULL AND save_path != ''")
            searchee_with_paths = cursor.fetchone()[0]
            f.write(f"client_searchee with paths: {searchee_with_paths}\n")
            
            # Check decision table
            cursor.execute("SELECT COUNT(*) FROM decision")
            decision_count = cursor.fetchone()[0]
            f.write(f"Total decision records: {decision_count}\n")
            
            # Check distinct decision types
            cursor.execute("SELECT decision, COUNT(*) FROM decision GROUP BY decision ORDER BY COUNT(*) DESC")
            decision_types = cursor.fetchall()
            f.write(f"Decision types:\n")
            for decision_type, count in decision_types:
                f.write(f"  {decision_type}: {count}\n")
            
            # Sample GUIDs and their tracker names
            f.write(f"\nSample GUIDs (first {limit}):\n")
            cursor.execute("SELECT DISTINCT guid FROM decision WHERE guid IS NOT NULL LIMIT ?", (limit,))
            for row in cursor.fetchall():
                guid = row[0]
                tracker_name = guid
                if guid.startswith("http"):
                    try:
                        parsed = urlparse(guid)
                        tracker_name = parsed.netloc  # e.g. www.torrentleech.org
                    except Exception:
                        pass
                normalized = normalize_tracker_name(tracker_name)
                f.write(f"  {guid} -> {tracker_name} -> {normalized}\n")
            
            # Check for successful matches
            success_placeholders = ','.join(['?' for _ in SUCCESS_DECISIONS])
            cursor.execute(f"SELECT COUNT(*) FROM decision WHERE decision IN ({success_placeholders})", SUCCESS_DECISIONS)
            success_count = cursor.fetchone()[0]
            f.write(f"\nSuccessful decisions ({', '.join(SUCCESS_DECISIONS)}): {success_count}\n")
            
            if success_count > 0:
                cursor.execute(f"""
                    SELECT d.guid, d.decision, COUNT(*)
                    FROM decision d
                    WHERE d.decision IN ({success_placeholders})
                    GROUP BY d.guid, d.decision
                    ORDER BY COUNT(*) DESC
                    LIMIT ?
                """, SUCCESS_DECISIONS + [limit])
                
                f.write("Top successful tracker/decision combinations:\n")
                for guid, decision, count in cursor.fetchall():
                    tracker_name = guid.split('.')[0] if '.' in guid else guid
                    normalized = normalize_tracker_name(tracker_name)
                    f.write(f"  {guid} ({normalized}) - {decision}: {count}\n")
            
            # Sample tracker URLs from client_searchee
            f.write(f"\nSample tracker URLs from client_searchee (first {limit}):\n")
            cursor.execute("""
                SELECT DISTINCT tracker, COUNT(*) as count 
                FROM client_searchee 
                WHERE tracker IS NOT NULL AND tracker != '' 
                GROUP BY tracker 
                ORDER BY count DESC 
                LIMIT ?
            """, (limit,))
            for tracker, count in cursor.fetchall():
                f.write(f"  {tracker}: {count}\n")
            
            f.write("=" * 50 + "\n")
        
        conn.close()
        print(f"🔍 Debug output written to: {debug_file}")
        
    except Exception as e:
        print(f"Error in debug function: {e}")

def main():
    parser = argparse.ArgumentParser(
        description= "Cross-Pollinator: Analyze your missing Torrents. Note this is a build line for existing torrents on trackers. If you need to change titling, add -tmdb TV/number or -tmdb movie/number or -tvdb number"
    )
    parser.add_argument('--run', action='store_true', help='Run analysis and show missing torrents')
    parser.add_argument('--output', nargs='?', const='default', help='Generate upload commands file (optional filename)')
    parser.add_argument('--no-emoji', action='store_true', help='Remove all emojis from output')
    parser.add_argument('--output-clean', action='store_true', help='Generate clean output with only upload commands. Add after --output')
    parser.add_argument('--debug', action='store_true', help='Show debug information about database content')
    
    args = parser.parse_args()
    
    if not args.run:
        parser.print_help()
        sys.exit(1)
    
    if not Path(DB_PATH).exists():
        msg = "Database not found" if args.no_emoji else "❌ Database not found"
        print(f"{msg}: {DB_PATH}")
        sys.exit(1)
    
    # Show debug info if requested
    if args.debug:
        debug_database_content()
        print()
    
    msg = "Analyzing cross-seed database for missing torrents..." if args.no_emoji else "🔍 Analyzing cross-seed database for missing torrents..."
    print(msg)
    results = get_torrents_with_paths()
    
    if not results:
        msg = "No torrents with paths found needing upload" if args.no_emoji else "✅ No torrents with paths found needing upload"
        print(msg)
        return
    
    msg = f"Found {len(results)} video files with paths needing upload" if args.no_emoji else f"📊 Found {len(results)} video files with paths needing upload"
    print(msg)
    
    # Display missing torrents and their trackers (skip if output-clean)
    if not args.output_clean:
        if args.no_emoji:
            print("\nMissing Video Files by Tracker:")
            print("=" * 80)
        else:
            print("\n🎬 Missing Video Files by Tracker:")
            print("=" * 80)
        
        for item in sorted(results, key=lambda x: x['name'].lower()):
            if args.no_emoji:
                print(f"\n{item['name']}")
                if item.get('duplicates'):
                    print(f"   Duplicates detected: {', '.join(item['duplicates'])}")
                print(f"   Path: {item['path']}")
                print(f"   Missing from: {', '.join(item['missing_trackers'])}")
                if item['found_trackers']:
                    print(f"   Found on: {', '.join(item['found_trackers'])}")
                else:
                    print(f"   Found on: None")
            else:
                print(f"\n🎬️  {item['name']}")
                if item.get('duplicates'):
                    print(f"   🔄 Duplicates detected: {', '.join(item['duplicates'])}")
                print(f"   📁 Path: {item['path']}")
                print(f"   ❌ Missing from: {', '.join(item['missing_trackers'])}")
                if item['found_trackers']:
                    print(f"   ✅ Found on: {', '.join(item['found_trackers'])}")
                else:
                    print(f"   ✅ Found on: None")
    
    # Generate upload commands only if --output is specified
    if args.output is not None:
        output_file = args.output if args.output != 'default' else None
        commands_file = generate_upload_commands(results, output_file, args.output_clean)
        if not args.output_clean:
            msg = f"Upload commands written to: {commands_file}" if args.no_emoji else f"📝 Upload commands written to: {commands_file}"
            print(f"\n{msg}")
            msg = f"Review {commands_file} before executing upload commands" if args.no_emoji else f"💡 Review {commands_file} before executing upload commands"
            print(msg)
    else:
        if not args.output_clean:
            msg = "Use --output to generate upload commands file" if args.no_emoji else f"💡 Use --output to generate upload commands file"
            print(f"\n{msg}")
    
    if not args.output_clean:
        msg = "Analysis complete!" if args.no_emoji else "\n✨ Analysis complete!"
        print(msg)

if __name__ == "__main__":
    main()
