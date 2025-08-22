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
    """Get torrents with their file paths and missing trackers using direct string search."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get all configured trackers from our mapping
        all_trackers = sorted(TRACKER_MAPPING.keys())
        if not all_trackers:
            return []
        
        print("📊 Getting torrents with paths and performing tracker string search...")
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
        
        print(f"Processing {total_torrents} torrents with direct string search...")
        
        results = []
        
        for i, (name, info_hash, save_path, trackers_text) in enumerate(torrents_data, 1):
            # Only process video files
            if not is_video_file(name):
                continue
            
            found_trackers = set()
            unmatched_trackers = []
            
            # Convert trackers to string for searching (handle None case)
            trackers_str = str(trackers_text).lower() if trackers_text else ""
            
            # Check each tracker abbreviation against the trackers string
            for tracker_abbrev, tracker_variants in TRACKER_MAPPING.items():
                tracker_found = False
                
                # Check if any variant of this tracker is in the trackers string
                for variant in tracker_variants:
                    if variant.lower() in trackers_str:
                        found_trackers.add(tracker_abbrev)
                        tracker_found = True
                        break
                
                # If no variant matched, collect unmatched tracker names for display
                if not tracker_found and trackers_str and trackers_str != "none":
                    # Extract individual tracker names from the JSON-like string for display
                    import re
                    # Find all domain-like strings in the trackers text
                    domains = re.findall(r'[\w.-]+\.[\w.-]+', trackers_str)
                    for domain in domains:
                        # Only add if it's not already covered by our mapping
                        domain_matched = False
                        for check_abbrev, check_variants in TRACKER_MAPPING.items():
                            if any(variant.lower() in domain.lower() for variant in check_variants):
                                domain_matched = True
                                break
                        if not domain_matched and domain not in unmatched_trackers:
                            unmatched_trackers.append(domain)
            
            # Calculate missing trackers
            missing_trackers = sorted(set(all_trackers) - found_trackers)
            
            # Only include torrents that are missing from some trackers
            if missing_trackers:
                # Create display list of found trackers
                found_display = sorted(found_trackers)
                if unmatched_trackers:
                    found_display.extend(sorted(unmatched_trackers))
                
                results.append({
                    'name': name,
                    'path': save_path,
                    'missing_trackers': missing_trackers,
                    'found_trackers': found_display
                })
            
            # Show progress every 25 items or on the last item
            if i % 25 == 0 or i == total_torrents:
                show_progress_bar(i, total_torrents, start_time)
        
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
