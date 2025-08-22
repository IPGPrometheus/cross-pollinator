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
import time

# Configuration
CROSS_SEED_DIR = "/cross-seed"
DB_PATH = "/cross-seed/cross-seed.db"

# Use environment variable or default to /logs (writable volume)
LOG_DIR = os.environ.get('CROSS_POLLINATOR_LOG_DIR', '/logs')

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
    'SP': ['SP', 'seedpool'],  # Added SeedPool mapping
    'STC': ['STC', 'skipthecommericals'],
    'THR': ['THR', 'torrenthr'],
    'TIK': ['TIK', 'cinematik'],
    'TL': ['TL', 'torrentleech'],  # Fixed TorrentLeech mapping
    'TOCA': ['TOCA', 'tocashare'],
    'UHD': ['UHD', 'uhdshare'],
    'ULCX': ['ULCX', 'upload'],
    'UTP': ['UTP'],
    'YOINK': ['YOINK', 'yoinked'],
    'YUS': ['YUS', 'yu-scene']
}

SUCCESS_DECISIONS = ['MATCH', 'MATCH_SIZE_ONLY', 'MATCH_PARTIAL', 'INFO_HASH_ALREADY_EXISTS']

def is_video_file(filename):
    """Check if filename has a video file extension."""
    video_extensions = {
        '.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v',
        '.mpg', '.mpeg', '.3gp', '.3g2', '.asf', '.rm', '.rmvb', '.vob',
        '.ts', '.mts', '.m2ts', '.divx', '.xvid', '.f4v', '.ogv'
    }
    return Path(filename).suffix.lower() in video_extensions

def normalize_tracker_name(raw_name):
    """Normalize tracker names to standard abbreviations."""
    try:
        name = raw_name.lower().strip()
        
        # Handle URL format
        if name.startswith('https://'):
            name = name[8:]
        elif name.startswith('http://'):
            name = name[7:]
        elif name.startswith('udp://'):
            name = name[6:]
        elif name.startswith('tracker://'):
            name = name[10:]
            
        # Remove API suffix
        if name.endswith(' (API)'):
            name = name[:-6]
        
        # Remove announce paths and parameters
        if '/announce' in name:
            name = name.split('/announce')[0]
        if '?' in name:
            name = name.split('?')[0]
        if ':' in name and not name.startswith('tracker.'):
            # Handle port numbers, but keep tracker. prefix
            name = name.split(':')[0]
            
        # Special handling for FileList
        if name.startswith('FileList-'):
            return 'FL'
        
        # Check for exact matches first
        for abbrev, variants in TRACKER_MAPPING.items():
            for variant in variants:
                if variant.lower() == name:
                    return abbrev
        
        # Extract domain from full URLs for further processing
        if '.' in name and '/' not in name:
            # This is likely a domain name
            domain_parts = name.split('.')
            if len(domain_parts) >= 2:
                # Handle special tracker domain patterns
                if name.startswith('tracker.'):
                    # For tracker.torrentleech.org -> torrentleech
                    main_domain = domain_parts[1] if len(domain_parts) > 2 else domain_parts[0]
                elif name.startswith('reactor.'):
                    # For reactor.filelist.io -> filelist
                    main_domain = domain_parts[1] if len(domain_parts) > 2 else domain_parts[0]
                elif domain_parts[0] == 'www':
                    # For www.torrentleech.org -> torrentleech
                    main_domain = domain_parts[1]
                else:
                    # For hawke.uno -> hawke
                    main_domain = domain_parts[0]
                
                # Check if the extracted main domain matches any variants
                for abbrev, variants in TRACKER_MAPPING.items():
                    for variant in variants:
                        if variant.lower() == main_domain:
                            return abbrev
        
        # Final check for substring matches (but be more specific)
        for abbrev, variants in TRACKER_MAPPING.items():
            for variant in variants:
                if len(variant) > 3 and variant.lower() in name:
                    return abbrev
        
        return 'Unknown'
    except Exception as e:
        print(f"Error normalizing tracker name '{raw_name}': {e}")
        return 'Unknown'

def get_all_configured_trackers():
    """Get all configured trackers from database decisions."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT guid FROM decision WHERE guid IS NOT NULL")
        trackers = set()
        
        for row in cursor.fetchall():
            guid = row[0]
            # Add safety check for guid format
            if '://' in guid and '/' in guid:
                tracker_name = guid.split('://')[1].split('/')[0]
                normalized = normalize_tracker_name(tracker_name)
                if normalized and normalized != 'Unknown':
                    trackers.add(normalized)
        
        conn.close()
        return sorted(trackers)
        
    except Exception as e:
        print(f"Error getting configured trackers: {e}")
        return []

def show_progress_bar(current, total, start_time, bar_length=50):
    """Display a simple progress bar with time estimates."""
    if total == 0:
        return
    
    elapsed = time.time() - start_time
    progress = current / total
    eta = (elapsed / progress) - elapsed if progress > 0 else 0
    
    # Create the bar
    filled = int(bar_length * progress)
    bar = '█' * filled + '░' * (bar_length - filled)
    
    # Format time
    elapsed_str = f"{elapsed:.1f}s"
    eta_str = f"{eta:.1f}s" if eta > 0 else "0.0s"
    
    # Print the progress bar
    print(f"\r[{bar}] {current}/{total} ({progress*100:.1f}%) | Elapsed: {elapsed_str} | ETA: {eta_str}", end='', flush=True)
    
    # Print newline when complete
    if current == total:
        print()

def get_torrents_with_paths():
    """Get torrents with their file paths and missing trackers."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        all_trackers = get_all_configured_trackers()
        if not all_trackers:
            return []
        
        print("📊 Getting torrents with paths and tracker info...")
        start_time = time.time()
        
        # Get torrents with paths and trackers column
        cursor.execute("""
            SELECT name, info_hash, save_path, trackers
            FROM client_searchee
            WHERE save_path IS NOT NULL AND save_path != ''
            ORDER BY name
        """)
        
        torrents_data = cursor.fetchall()
        total_torrents = len(torrents_data)
        
        name_to_info = defaultdict(lambda: {'info_hashes': set(), 'paths': set(), 'found_trackers': set(), 'found_domains': set()})
        
        print(f"Processing {total_torrents} torrents...")
        for i, (name, info_hash, save_path, trackers_json) in enumerate(torrents_data, 1):
            name_to_info[name]['info_hashes'].add(info_hash)
            name_to_info[name]['paths'].add(save_path)
            
            # Parse trackers JSON and normalize tracker names
            if trackers_json:
                try:
                    import json
                    trackers_list = json.loads(trackers_json)
                    for tracker in trackers_list:
                        normalized = normalize_tracker_name(tracker)
                        if normalized and normalized != 'Unknown':
                            name_to_info[name]['found_trackers'].add(normalized)
                        else:
                            # Keep original tracker name if we can't normalize it
                            name_to_info[name]['found_domains'].add(tracker)
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"Error parsing trackers JSON for {name}: {e}")
                    # Fallback: treat as plain string if it's not JSON
                    if isinstance(trackers_json, str) and trackers_json.strip():
                        normalized = normalize_tracker_name(trackers_json.strip())
                        if normalized and normalized != 'Unknown':
                            name_to_info[name]['found_trackers'].add(normalized)
                        else:
                            name_to_info[name]['found_domains'].add(trackers_json.strip())
            
            # Show progress every 10 items or on the last item
            if i % 10 == 0 or i == total_torrents:
                show_progress_bar(i, total_torrents, start_time)
        
        print("🎬 Filtering video files and building results...")
        filter_start_time = time.time()
        
        # Build results with missing trackers (filter for video files only)
        results = []
        items_to_process = list(name_to_info.items())
        total_items = len(items_to_process)
        
        for i, (name, info) in enumerate(items_to_process, 1):
            # Only include video files
            if not is_video_file(name):
                continue
                
            missing_trackers = sorted(set(all_trackers) - info['found_trackers'])
            if missing_trackers and info['paths']:
                # Use the first available path
                file_path = list(info['paths'])[0]
                
                # Combine found trackers and domains for display
                found_display = sorted(info['found_trackers'])
                if info['found_domains']:
                    found_display.extend(sorted(info['found_domains']))
                
                results.append({
                    'name': name,
                    'path': file_path,
                    'missing_trackers': missing_trackers,
                    'found_trackers': found_display
                })
            
            # Show progress every 25 items or on the last item
            if i % 25 == 0 or i == total_items:
                show_progress_bar(i, total_items, filter_start_time)
        
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
    
    with open(filename, 'w') as f:
        if not clean_output:
            f.write(f"# Cross-Pollinator: Generated {datetime.now()}\n")
            f.write(f"# Total files needing upload: {len(results)}\n Note this is a build line for existing torrents on trackers. \n If you need to change anything, please add -tmdb TV/number or -tmdb movie/number or -tvdb number \n\n")
        
        for item in sorted(results, key=lambda x: x['name'].lower()):
            if not clean_output:
                f.write(f"# {item['name']}\n")
                f.write(f"# Missing from: {', '.join(item['missing_trackers'])}\n")
                f.write(f"# Found on: {', '.join(item['found_trackers']) if item['found_trackers'] else 'None'}\n")
            
            # Construct the full file path by combining directory and filename
            base_path = Path(item["path"])
            torrent_name = item["name"]
            
            # Construct full path: directory + torrent name
            full_file_path = base_path / torrent_name
            
            # Create the tracker list parameter
            tracker_list = ','.join(item['missing_trackers'])
            
            f.write(f'python3 upload.py "{full_file_path}" --trackers {tracker_list}\n')
            if not clean_output:
                f.write('\n')

    print(f"✅ Upload commands written to: {filename}")
    return filename

def main():
    parser = argparse.ArgumentParser(
        description= "Cross-Pollinator: Analyze your missing Torrents. Note this is a build line for existing torrents on trackers. If you need to change anything, please add -tmdb TV/number or -tmdb movie/number or -tvdb number"
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
                print(f"   Path: {item['path']}")
                print(f"   Missing from: {', '.join(item['missing_trackers'])}")
                if item['found_trackers']:
                    print(f"   Found on: {', '.join(item['found_trackers'])}")
                else:
                    print(f"   Found on: None")
            else:
                print(f"\n🎬️  {item['name']}")
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
