#!/usr/bin/env python3
"""
Cross-Pollinator Uploader - Generate Upload Commands (Refactored)

Parses cross-seed database using client_searchee table to find missing trackers.
Uses info_hash to match torrents and trackers column to determine missing trackers.
"""
import os
import sqlite3
import sys
import argparse
import json
from collections import defaultdict
from pathlib import Path
from datetime import datetime
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
    
    return False

def normalize_tracker_url(tracker_url):
    """Normalize tracker URL to standard abbreviation."""
    if not tracker_url:
        return None
        
    url_lower = tracker_url.lower().strip()
    
    # Handle special cases first
    if 'filelist' in url_lower:
        return 'FL'
    
    # Extract domain from URL
    domain = url_lower
    if url_lower.startswith('http'):
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url_lower)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
        except Exception:
            pass
    
    # Match against TRACKER_MAPPING
    for abbrev, variants in TRACKER_MAPPING.items():
        for variant in variants:
            variant_lower = variant.lower()
            if variant_lower in domain or domain in variant_lower:
                return abbrev
    
    return None

def get_all_unique_trackers():
    """Get all unique trackers from client_searchee.trackers column."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("Getting all unique trackers from database...")
        
        # Get all tracker JSON arrays from client_searchee
        cursor.execute("""
            SELECT DISTINCT trackers 
            FROM client_searchee 
            WHERE trackers IS NOT NULL 
            AND trackers != ''
            AND trackers != '[]'
        """)
        
        all_trackers = set()
        tracker_rows = cursor.fetchall()
        
        for row in tracker_rows:
            trackers_json = row[0]
            try:
                tracker_list = json.loads(trackers_json)
                for tracker_url in tracker_list:
                    normalized = normalize_tracker_url(tracker_url)
                    if normalized:
                        all_trackers.add(normalized)
            except json.JSONDecodeError:
                continue
        
        conn.close()
        return sorted(all_trackers)
        
    except Exception as e:
        print(f"Error getting unique trackers: {e}")
        return []

def filter_relevant_trackers(all_trackers, filename):
    """Filter trackers based on content type."""
    is_anime = is_anime_content(filename)
    
    if is_anime:
        # For anime, include anime trackers and exclude general movie/TV trackers
        return sorted(set(all_trackers) & (ANIME_TRACKERS | (set(all_trackers) - GENERAL_TRACKERS)))
    else:
        # For non-anime, exclude anime-specific trackers
        return sorted(set(all_trackers) - ANIME_TRACKERS)

def normalize_content_name(filename):
    """Normalize content name for duplicate detection."""
    name = Path(filename).stem

    quality_patterns = [
        r'\.\d{3,4}p\.',
        r'\.BluRay\.',
        r'\.WEB-DL\.',
        r'\.WEBRip\.',
        r'\.BDRip\.',
        r'\.DVDRip\.',
        r'\.AMZN\.',
        r'\.FLUX\.',
        r'\.ATMOS\.',
        r'\.DDP\d+\.\d+\.',
        r'\.H\.264-',
        r'\.x264-',
        r'\.x265-',
        r'-[A-Z0-9]+$',
    ]

    normalized = name
    for pattern in quality_patterns:
        normalized = re.sub(pattern, '.', normalized, flags=re.IGNORECASE)

    normalized = re.sub(r'\.+', '.', normalized).strip('.')
    return normalized.lower()

def analyze_missing_trackers():
    """Main function to analyze missing trackers using client_searchee table."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get all unique trackers first
        print("Step 1: Getting all configured trackers...")
        all_trackers = get_all_unique_trackers()
        
        if not all_trackers:
            print("No trackers found in database")
            return []
        
        print(f"Found {len(all_trackers)} unique trackers: {', '.join(all_trackers)}")
        
        # Get all torrents with their tracker lists and paths
        print("\nStep 2: Analyzing torrents and their tracker coverage...")
        cursor.execute("""
            SELECT name, info_hash, save_path, trackers
            FROM client_searchee
            WHERE save_path IS NOT NULL 
            AND save_path != ''
            AND trackers IS NOT NULL
            AND trackers != ''
            AND trackers != '[]'
            ORDER BY name
        """)
        
        torrent_rows = cursor.fetchall()
        total_torrents = len(torrent_rows)
        
        if total_torrents == 0:
            print("No torrents with paths and trackers found")
            return []
        
        print(f"Found {total_torrents} torrents to analyze")
        
        results = []
        content_groups = defaultdict(list)  # Group by normalized name to handle duplicates
        start_time = time.time()
        
        # Process each torrent
        for i, row in enumerate(torrent_rows):
            print_progress_bar(i + 1, total_torrents, start_time, "Processing torrents")
            
            name, info_hash, save_path, trackers_json = row
            
            # Only process video files
            if not is_video_file(name):
                continue
            
            try:
                # Parse the trackers JSON
                current_trackers = json.loads(trackers_json)
                
                # Normalize tracker URLs to abbreviations
                found_trackers = set()
                for tracker_url in current_trackers:
                    normalized = normalize_tracker_url(tracker_url)
                    if normalized:
                        found_trackers.add(normalized)
                
                # Filter relevant trackers for this content
                relevant_trackers = filter_relevant_trackers(all_trackers, name)
                
                # Find missing trackers
                missing_trackers = sorted(set(relevant_trackers) - found_trackers)
                
                if missing_trackers:
                    # Group by normalized name to handle duplicates
                    normalized_name = normalize_content_name(name)
                    content_groups[normalized_name].append({
                        'name': name,
                        'info_hash': info_hash,
                        'path': save_path,
                        'missing_trackers': missing_trackers,
                        'found_trackers': sorted(found_trackers & set(relevant_trackers)),
                        'normalized_name': normalized_name
                    })
                    
            except json.JSONDecodeError:
                # Skip torrents with invalid JSON
                continue
        
        print()  # New line after progress bar
        
        # Process content groups and handle duplicates
        print("Step 3: Processing content groups and handling duplicates...")
        processed_content = set()
        
        for normalized_name, items in content_groups.items():
            if normalized_name in processed_content:
                continue
            
            if len(items) > 1:
                # Handle duplicates - merge found trackers and use primary item
                merged_found_trackers = set()
                for item in items:
                    merged_found_trackers.update(item['found_trackers'])
                
                # Use first item as primary and update its found trackers
                primary_item = items[0]
                relevant_trackers = filter_relevant_trackers(all_trackers, primary_item['name'])
                missing_trackers = sorted(set(relevant_trackers) - merged_found_trackers)
                
                if missing_trackers:
                    primary_item['missing_trackers'] = missing_trackers
                    primary_item['found_trackers'] = sorted(merged_found_trackers & set(relevant_trackers))
                    primary_item['duplicates'] = [item['name'] for item in items]
                    results.append(primary_item)
            else:
                # Single item
                if items[0]['missing_trackers']:
                    results.append(items[0])
            
            processed_content.add(normalized_name)
        
        conn.close()
        return results
        
    except Exception as e:
        print(f"Error analyzing missing trackers: {e}")
        return []

def generate_upload_commands(results, output_file=None, clean_output=False):
    """Generate upload.py commands and save them to persistent appdata."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Ensure LOG_DIR is a Path object for consistency
    appdata_dir = Path(LOG_DIR)
    appdata_dir.mkdir(parents=True, exist_ok=True)

    if output_file:
        filename = appdata_dir / Path(output_file).name
    else:
        filename = appdata_dir / f"upload_commands_{timestamp}.txt"
    
    print("Generating upload commands...")
    start_time = time.time()
    
    with open(filename, 'w') as f:
        if not clean_output:
            f.write(f"# Cross-Pollinator: Generated {datetime.now()}\n")
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
            full_file_path = base_path / torrent_name
            
            # Create the tracker list parameter - only include missing trackers
            tracker_list = ','.join(item['missing_trackers'])
            
            f.write(f'python3 upload.py "{full_file_path}" --trackers {tracker_list}\n')
            if not clean_output:
                f.write('\n')
    
    print()  # New line after progress bar
    print(f"Upload commands written to: {filename}")
    return filename

def debug_database_content(limit=10):
    """Debug function to inspect database content."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    appdata_dir = Path(LOG_DIR)
    appdata_dir.mkdir(parents=True, exist_ok=True)
    debug_file = appdata_dir / f"debug_output_{timestamp}.txt"
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        with open(debug_file, 'w') as f:
            f.write("DEBUG: Cross-Seed Database Analysis\n")
            f.write("=" * 50 + "\n")
            
            # Check client_searchee table structure
            cursor.execute("PRAGMA table_info(client_searchee)")
            columns = cursor.fetchall()
            f.write("client_searchee table columns:\n")
            for col in columns:
                f.write(f"  {col[1]} ({col[2]})\n")
            
            # Count records
            cursor.execute("SELECT COUNT(*) FROM client_searchee")
            total_count = cursor.fetchone()[0]
            f.write(f"\nTotal client_searchee records: {total_count}\n")
            
            cursor.execute("SELECT COUNT(*) FROM client_searchee WHERE save_path IS NOT NULL AND save_path != ''")
            with_paths = cursor.fetchone()[0]
            f.write(f"Records with save_path: {with_paths}\n")
            
            cursor.execute("SELECT COUNT(*) FROM client_searchee WHERE trackers IS NOT NULL AND trackers != '' AND trackers != '[]'")
            with_trackers = cursor.fetchone()[0]
            f.write(f"Records with trackers: {with_trackers}\n")
            
            # Sample tracker data
            f.write(f"\nSample tracker data (first {limit}):\n")
            cursor.execute("""
                SELECT name, trackers 
                FROM client_searchee 
                WHERE trackers IS NOT NULL 
                AND trackers != '' 
                AND trackers != '[]'
                LIMIT ?
            """, (limit,))
            
            for name, trackers_json in cursor.fetchall():
                try:
                    trackers = json.loads(trackers_json)
                    f.write(f"  {name}:\n")
                    for tracker in trackers:
                        normalized = normalize_tracker_url(tracker)
                        f.write(f"    {tracker} -> {normalized}\n")
                except json.JSONDecodeError:
                    f.write(f"  {name}: Invalid JSON\n")
            
            # Unique trackers summary
            all_trackers = get_all_unique_trackers()
            f.write(f"\nUnique normalized trackers ({len(all_trackers)}):\n")
            f.write(f"  {', '.join(all_trackers)}\n")
            
        conn.close()
        print(f"Debug output written to: {debug_file}")
        
    except Exception as e:
        print(f"Error in debug function: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Cross-Pollinator: Analyze missing torrents using cross-seed database"
    )
    parser.add_argument('--run', action='store_true', help='Run analysis and show missing torrents')
    parser.add_argument('--output', nargs='?', const='default', help='Generate upload commands file (optional filename)')
    parser.add_argument('--no-emoji', action='store_true', help='Remove all emojis from output')
    parser.add_argument('--output-clean', action='store_true', help='Generate clean output with only upload commands')
    parser.add_argument('--debug', action='store_true', help='Show debug information about database content')
    
    args = parser.parse_args()
    
    if not args.run:
        parser.print_help()
        sys.exit(1)
    
    if not Path(DB_PATH).exists():
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)
    
    # Show debug info if requested
    if args.debug:
        debug_database_content()
        print()
    
    print("Analyzing cross-seed database for missing torrents...")
    results = analyze_missing_trackers()
    
    if not results:
        print("No torrents found needing upload to additional trackers")
        return
    
    print(f"Found {len(results)} video files needing upload to additional trackers")
    
    # Display results unless clean output requested
    if not args.output_clean:
        print("\nMissing Video Files by Tracker:")
        print("=" * 80)
        
        for item in sorted(results, key=lambda x: x['name'].lower()):
            print(f"\n{item['name']}")
            if item.get('duplicates'):
                print(f"   Duplicates detected: {', '.join(item['duplicates'])}")
            print(f"   Path: {item['path']}")
            print(f"   Missing from: {', '.join(item['missing_trackers'])}")
            if item['found_trackers']:
                print(f"   Found on: {', '.join(item['found_trackers'])}")
            else:
                print(f"   Found on: None")
    
    # Generate upload commands if requested
    if args.output is not None:
        output_file = args.output if args.output != 'default' else None
        commands_file = generate_upload_commands(results, output_file, args.output_clean)
        if not args.output_clean:
            print(f"\nUpload commands written to: {commands_file}")
            print("Review the file before executing upload commands")
    elif not args.output_clean:
        print("\nUse --output to generate upload commands file")
    
    if not args.output_clean:
        print("\nAnalysis complete!")

if __name__ == "__main__":
    main()
