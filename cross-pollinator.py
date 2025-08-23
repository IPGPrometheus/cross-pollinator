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

SUCCESS_DECISIONS = ['MATCH', 'MATCH_SIZE_ONLY', 'MATCH_PARTIAL', 'INFO_HASH_ALREADY_EXISTS']

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
    """Normalize tracker names to standard abbreviations."""
    name = raw_name.strip()
    
    if name.startswith('https://'):
        name = name[8:]
    if name.endswith(' (API)'):
        name = name[:-6]
    if name.startswith('FileList-'):
        return 'FL'
    
    # Special handling for tracker URLs (common in client_searchee)
    if 'tleechreload.org' in name or 'torrentleech.org' in name:
        return 'TL'
    if 'blutopia.cc' in name:
        return 'BLU'
    if 'beyond-hd.me' in name:
        return 'BHD'
    if 'aither.cc' in name:
        return 'AITHER'
    if 'anthelion.me' in name:
        return 'ANT'
    if 'hdbits.org' in name:
        return 'HDB'
    if 'passthepopcorn.me' in name:
        return 'PTP'
    if 'morethantv.me' in name:
        return 'MTV'
    if 'cathode-ray.tube' in name:
        return 'CRT'
    
    for abbrev, variants in TRACKER_MAPPING.items():
        if name in variants or name.lower() in [v.lower() for v in variants]:
            return abbrev
    
    return None

def normalize_content_name(filename):
    """Normalize content name for duplicate detection."""
    # Remove file extension
    name = Path(filename).stem
    
    # Remove common quality/format indicators
    quality_patterns = [
        r'\.\d{3,4}p\.',  # .1080p., .720p., etc.
        r'\.BluRay\.',
        r'\.WEB-DL\.',
        r'\.WEBRip\.',
        r'\.BDRip\.',
        r'\.DVDRip\.',
        r'\.AMZN\.',
        r'\.FLUX\.',
        r'\.ATMOS\.',
        r'\.DDP\d+\.\d+\.',  # .DDP5.1.
        r'\.H\.264-',
        r'\.x264-',
        r'\.x265-',
        r'-[A-Z0-9]+$',  # Release group at end
    ]
    
    normalized = name
    for pattern in quality_patterns:
        normalized = re.sub(pattern, '.', normalized, flags=re.IGNORECASE)
    
    # Clean up multiple dots and normalize
    normalized = re.sub(r'\.+', '.', normalized)
    normalized = normalized.strip('.')
    
    return normalized.lower()

def get_active_trackers():
    """Get trackers that you actually have successful uploads/downloads on."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get trackers where you have successful matches (indicating you're active on them)
        cursor.execute("""
            SELECT DISTINCT guid 
            FROM decision 
            WHERE decision IN ('MATCH', 'MATCH_SIZE_ONLY', 'MATCH_PARTIAL', 'INFO_HASH_ALREADY_EXISTS')
            AND guid IS NOT NULL
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
        
        # Process torrents with progress bar
        for i, row in enumerate(torrent_rows):
            print_progress_bar(i + 1, total_torrents, start_time, "Processing torrents")
            name, info_hash, save_path = row
            name_to_info[name]['info_hashes'].add(info_hash)
            name_to_info[name]['paths'].add(save_path)
        
        print()  # New line after progress bar
        
        # Get all decisions for better tracker matching
        print("🔄 Analyzing tracker decisions...")
        cursor.execute("""
            SELECT d.info_hash, d.guid, d.decision, cs.name
            FROM decision d
            JOIN client_searchee cs ON d.info_hash = cs.info_hash
            WHERE d.guid IS NOT NULL
            ORDER BY d.last_seen DESC
        """)
        
        decision_rows = cursor.fetchall()
        total_decisions = len(decision_rows)
        
        # Process decisions with progress bar
        decision_start = time.time()
        processed_pairs = set()  # Track processed (info_hash, guid) pairs
        
        for i, row in enumerate(decision_rows):
            if i % 100 == 0 or i == total_decisions - 1:  # Update every 100 decisions or at the end
                print_progress_bar(i + 1, total_decisions, decision_start, "Processing decisions")
            
            info_hash, guid, decision, torrent_name = row
            pair_key = (info_hash, guid)
            
            # Skip if we've already processed this info_hash/tracker combination (keeps latest)
            if pair_key in processed_pairs:
                continue
            processed_pairs.add(pair_key)
            
            tracker_name = guid.split('.')[0] if '.' in guid else guid
            normalized = normalize_tracker_name(tracker_name)
            
            if not normalized:
                continue
            
            # Find the matching torrent name and update its found_trackers
            if torrent_name in name_to_info and decision in SUCCESS_DECISIONS:
                name_to_info[torrent_name]['found_trackers'].add(normalized)
        
        print()  # New line after progress bar
        
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

def main():
    parser = argparse.ArgumentParser(
        description= "Cross-Pollinator: Analyze your missing Torrents. Note this is a build line for existing torrents on trackers. If you need to change titling, add -tmdb TV/number or -tmdb movie/number or -tvdb number"
    )
    parser.add_argument('--run', action='store_true', help='Run analysis and show missing torrents')
    parser.add_argument('--output', nargs='?', const='default', help='Generate upload commands file (optional filename)')
    parser.add_argument('--no-emoji', action='store_true', help='Remove all emojis from output')
    parser.add_argument('--output-clean', action='store_true', help='Generate clean output with only upload commands. Add after --output')
    
    args = parser.parse_args()
    
    if not args.run:
        parser.print_help()
        sys.exit(1)
    
    if not Path(DB_PATH).exists():
        msg = "Database not found" if args.no_emoji else "❌ Database not found"
        print(f"{msg}: {DB_PATH}")
        sys.exit(1)
    
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
