#!/usr/bin/env python3
"""
Cross-Pollinator Uploader - Generate Upload Commands (Improved Tracker Mapping)

Parses cross-seed database using client_searchee table to find missing trackers.
Uses info_hash to match torrents and trackers column to determine missing trackers.
"""
import os
import sqlite3
import sys
import argparse
import json
import configparser
from collections import defaultdict
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import re
import time

load_dotenv()

# Configuration
# Look for the cross-seed directory from an environment variable,
# default to /cross-seed for Docker compatibility.
CROSS_SEED_DIR = os.environ.get('CROSS_SEED_DIR', '/cross-seed')
DB_PATH = os.path.join(CROSS_SEED_DIR, 'cross-seed.db')
LOG_DIR = os.environ.get('CROSS_POLLINATOR_LOG_DIR', '/logs')
CONFIG_DIR = os.environ.get('CROSS_POLLINATOR_CONFIG_DIR', 'config')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'cross-pollinator-config.ini')

# Comprehensive tracker mapping - Updated with exact domain matches first
TRACKER_MAPPING = {
    'ACM': ['ACM', 'eiga'],
    'AT': ['AT', 'animetorrents.me'],
    'ABT': ['ABT', 'tracker.animebytes.tv'],
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
    'BTN': ['BTN', 'broadcasthe.net', 'landof.tv'],
    'CBR': ['CBR', 'capybarabr'],
    'CRT': ['CRT', 'cathode-ray.tube', 'signal.cathode-ray.tube'],
    'CG': ['CG', 'cinemageddon'],
    'CHD': ['CHD', 'chdbits'],
    'CinemaZ': ['CinemaZ', 'cinemaz'],
    'DCC': ['DCC', 'digitalcore.club'],
    'DT': ['DT', 'desitorrents'],
    'DP': ['DP', 'darkpeers'],
    'EMT': ['EMT', 'empornium'],
    'FNP': ['FNP', 'fearnopeer'],
    'FL': ['FL', 'filelist', 'FileList', 'reactor.filelist.io', 'reactor.thefl.org', 'reactor.flro.org'],
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
    'HDS': ['HDS', 'hd-space.pw'],
    'HUNO': ['HUNO', 'hawke', 'hawke.uno'],
    'iAnon': ['iAnon'],
    'IMS': ['IMS', 'immortalseed.me'],
    'ICE': ['ICE', 'icetorrent'],
    'IPT': ['IPT', 'localhost.stackoverflow.tech', 'routing.bgp.technology','ssl.empirehost.me'],
    'ITT': ['ITT', 'itatorrents'],
    'JPopsuki': ['JPopsuki'],
    'KG': ['KG', 'karagarga'],
    'LCD': ['LCD', 'locadora'],
    'LST': ['LST', 'lst', 'lst.gg'],
    'LT': ['LT', 'lat-team'],
    'MAM': ['MAM', 'myanonamouse'],
    'ME': ['ME', 'milkie'],
    'MTV': ['MTV', 'morethantv', 'morethantv.me'],
    'MTeam': ['MTeam'],
    'NBL': ['NBL', 'nebulance'],
    'NC': ['NC', 'norbits'],
    'NM': ['NM', 'nostream'],
    'OE': ['OE', 'onlyencodes', 'onlyencodes.cc'],
    'OPS': ['OPS', 'orpheus', 'home.opsfet.ch'],
    'OTW': ['OTW', 'oldtoons', 'oldtoons.world'],
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
    'RED': ['RED', 'redacted', 'flacsfor.me'],
    'RF': ['RF', 'reelflix'],
    'RTF': ['RTF', 'retroflix'],
    'SAM': ['SAM', 'samaritano'],
    'SC': ['SC', 'scenetime'],
    'SPC': ['SPC', 'sportscult-announce.org'],
    'SN': ['SN', 'swarmazon'],
    'SB': ['SB', 'superbits.org:2086','tracker.superbits.org:2086'],
    'SP': ['SP', 'seedpool.org'],
    'SPD': ['SPD', 'speed.connecting.center'],
    'SPI': ['SPI', 'scenepalace.info'],
    'STC': ['STC', 'skipthecommericals'],
    'THC': ['THC', 'thehorrorcult'],
    'THR': ['THR', 'torrenthr'],
    'TIK': ['TIK', 'cinematik'],
    'TL': ['TL', 'torrentleech', 'tleechreload.org', 'torrentleech.org', 'tracker.tleechreload.org', 'tracker.torrentleech.org'],
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
    'XWT': ['XWT', 'tracker.xtremewrestlingtorrents.net','xtremewrestlingtorrents.net'],
    'YOINK': ['YOINK', 'yoinked'],
    'YUS': ['YUS', 'yu-scene']
}

def create_default_config(available_trackers=None):
    """Create a default configuration file."""
    config = configparser.ConfigParser()
    
    # Use available trackers if provided, otherwise use a default list
    default_trackers = ','.join(available_trackers) if available_trackers else 'BLU,AITHER,ANT,BHD,MTV,FL,TL,BTN,PHD'
    
    # Default configuration sections
    config['TRACKERS'] = {
        'enabled_trackers': default_trackers,
        'disabled_trackers': '',
        'comment': '# Comma-separated list of tracker abbreviations to include/exclude'
    }
    
    config['FILTERING'] = {
        'include_single_episodes': 'false',
        'exclude_single_episodes': 'true',
        'single_episode_patterns': 'S\d{2}E\d{2},EP?\d+,Episode\s*\d+,\d{4}[.\-]\d{2}[.\-]\d{2}',
        'comment': '# Set include_single_episodes=true to include single episodes, false to exclude'
    }
    
    config['GENERAL'] = {
        'auto_filter_categories': 'false',
        'default_categories': 'Movies,TV',
        'comment': '# Set auto_filter_categories=true to automatically filter by default_categories'
    }
    
    return config

def load_config(available_trackers=None):
    """Load configuration from file, create default if doesn't exist."""
    config_path = Path(CONFIG_FILE)
    config = configparser.ConfigParser()
    
    if not config_path.exists():
        print(f"Configuration file not found. Creating default config at: {CONFIG_FILE}")
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        default_config = create_default_config(available_trackers)
        with open(config_path, 'w') as f:
            default_config.write(f)
        config = default_config
    else:
        config.read(config_path)
        
        # Ensure all required sections exist
        if 'TRACKERS' not in config:
            config['TRACKERS'] = {'enabled_trackers': '', 'disabled_trackers': ''}
        if 'FILTERING' not in config:
            config['FILTERING'] = {'include_single_episodes': 'false', 'exclude_single_episodes': 'true'}
        if 'GENERAL' not in config:
            config['GENERAL'] = {'auto_filter_categories': 'false', 'default_categories': 'Movies,TV'}
    
    return config

def get_enabled_trackers_from_config(config, available_trackers):
    """Get list of enabled trackers based on configuration."""
    enabled_list = config['TRACKERS'].get('enabled_trackers', '').strip()
    disabled_list = config['TRACKERS'].get('disabled_trackers', '').strip()
    
    if enabled_list:
        # If enabled_trackers is specified, only use those
        enabled = [t.strip().upper() for t in enabled_list.split(',') if t.strip()]
        result = [t for t in enabled if t in available_trackers]
        print(f"Using enabled trackers from config: {', '.join(result)}")
        return result
    elif disabled_list:
        # If disabled_trackers is specified, exclude those from available
        disabled = [t.strip().upper() for t in disabled_list.split(',') if t.strip()]
        result = [t for t in available_trackers if t not in disabled]
        print(f"Excluding disabled trackers from config: {', '.join(disabled)}")
        print(f"Remaining trackers: {', '.join(result)}")
        return result
    else:
        # If no tracker filtering specified, use all available
        print("No tracker filtering specified in config, using all available trackers")
        return available_trackers

def is_single_episode(filename, config):
    """Check if filename appears to be a single episode based on config patterns."""
    patterns = config['FILTERING'].get('single_episode_patterns', 'S\d{2}E\d{2},EP?\d+,Episode\s*\d+,\d{4}[.\-]\d{2}[.\-]\d{2}').split(',')
    filename_lower = filename.lower()
    
    for pattern in patterns:
        pattern = pattern.strip()
        if pattern and re.search(pattern, filename_lower, re.IGNORECASE):
            return True
    
    return False

def should_include_single_episodes(config):
    """Check if single episodes should be included based on config."""
    include = config['FILTERING'].getboolean('include_single_episodes', fallback=False)
    exclude = config['FILTERING'].getboolean('exclude_single_episodes', fallback=True)
    
    # If both are set, exclude takes precedence
    if exclude:
        return False
    return include

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

def extract_unique_trackers_from_db():
    """Extract all unique tracker domains from the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("Extracting unique trackers from database...")
        
        # Get all tracker data from database
        cursor.execute("""
            SELECT DISTINCT trackers
            FROM client_searchee
            WHERE trackers IS NOT NULL 
            AND trackers != ''
            AND trackers != '[]'
        """)
        
        unique_domains = set()
        tracker_combinations = cursor.fetchall()
        
        for (trackers_json,) in tracker_combinations:
            try:
                trackers_list = json.loads(trackers_json)
                for domain in trackers_list:
                    if domain and isinstance(domain, str):
                        unique_domains.add(domain.strip())
            except json.JSONDecodeError:
                continue
        
        conn.close()
        return sorted(unique_domains)
        
    except Exception as e:
        print(f"Error extracting unique trackers: {e}")
        return []

def extract_unique_categories_from_db():
    """Extract all unique categories from the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("Extracting unique categories from database...")
        
        # Get all categories from database
        cursor.execute("""
            SELECT DISTINCT category
            FROM client_searchee
            WHERE category IS NOT NULL 
            AND category != ''
        """)
        
        unique_categories = set()
        category_rows = cursor.fetchall()
        
        for (category,) in category_rows:
            if category:
                # Handle both single categories and comma-separated lists
                categories = [cat.strip() for cat in str(category).split(',') if cat.strip()]
                unique_categories.update(categories)
        
        conn.close()
        return sorted(unique_categories)
        
    except Exception as e:
        print(f"Error extracting unique categories: {e}")
        return []

def map_domain_to_abbreviation(domain):
    """Map a tracker domain to its abbreviation using TRACKER_MAPPING with improved matching."""
    if not domain:
        return None
    
    domain_lower = domain.lower().strip()
    
    # Create a list of (abbrev, variant) tuples sorted by variant length (longest first)
    # This ensures exact matches are tried before partial matches
    matches = []
    for abbrev, variants in TRACKER_MAPPING.items():
        for variant in variants:
            matches.append((abbrev, variant.lower()))
    
    # Sort by variant length (descending) to prioritize exact/longer matches
    matches.sort(key=lambda x: len(x[1]), reverse=True)
    
    # Try exact matches first
    for abbrev, variant in matches:
        if domain_lower == variant:
            return abbrev
    
    # Try partial matches (variant contained in domain) - for tracker.domain.org cases
    for abbrev, variant in matches:
        if variant in domain_lower and len(variant) > 3:  # Avoid very short partial matches
            return abbrev
    
    # Try reverse partial matches (domain contained in variant) - be very conservative
    for abbrev, variant in matches:
        if domain_lower in variant and len(domain_lower) > 5:  # Only for longer domains
            return abbrev
    
    return None

def build_comprehensive_tracker_mapping():
    """Build a comprehensive mapping of all database domains to abbreviations."""
    print("Step 1: Building comprehensive tracker mapping...")
    
    # Get all unique domains from database
    unique_domains = extract_unique_trackers_from_db()
    print(f"Found {len(unique_domains)} unique tracker domains in database")
    
    # Map domains to abbreviations
    domain_to_abbrev = {}
    mapped_trackers = set()
    unknown_domains = []
    
    for domain in unique_domains:
        abbrev = map_domain_to_abbreviation(domain)
        if abbrev:
            domain_to_abbrev[domain] = abbrev
            mapped_trackers.add(abbrev)
        else:
            unknown_domains.append(domain)
    
    print(f"Successfully mapped {len(domain_to_abbrev)} domains to {len(mapped_trackers)} tracker abbreviations")
    print(f"Mapped trackers: {', '.join(sorted(mapped_trackers))}")
    
    if unknown_domains:
        print(f"\nWarning: {len(unknown_domains)} domains could not be mapped:")
        for domain in sorted(unknown_domains):
            print(f"  - {domain}")
        print("\nConsider adding these to TRACKER_MAPPING if they are valid trackers")
    
    return domain_to_abbrev, sorted(mapped_trackers)

def get_available_trackers_from_mapping():
    """Get list of trackers that are available based on what's actually in the database."""
    _, mapped_trackers = build_comprehensive_tracker_mapping()
    return mapped_trackers

def filter_relevant_trackers(all_trackers, filename=None, available_trackers=None):
    """Filter trackers based on available trackers only (removed content type filtering)."""
    # If available_trackers is provided, only consider those trackers
    if available_trackers:
        candidate_trackers = set(all_trackers) & set(available_trackers)
    else:
        candidate_trackers = set(all_trackers)
    
    # Return all available trackers - no content-based filtering
    return sorted(candidate_trackers)

def prompt_category_filter(available_categories, config):
    """Prompt user to select which categories to filter by."""
    if not available_categories:
        return None
    
    # Check if auto-filtering is enabled
    if config['GENERAL'].getboolean('auto_filter_categories', fallback=False):
        default_cats = config['GENERAL'].get('default_categories', 'Movies,TV').split(',')
        default_cats = [cat.strip() for cat in default_cats if cat.strip()]
        valid_defaults = [cat for cat in default_cats if cat in available_categories]
        if valid_defaults:
            print(f"Auto-filtering enabled. Using categories: {', '.join(valid_defaults)}")
            return valid_defaults
    
    print(f"\nFound categories: {', '.join(available_categories)}")
    print("\nDo you want to filter by all categories? Y/N")
    
    while True:
        choice = input().strip().upper()
        if choice == 'Y':
            return available_categories  # Return all categories
        elif choice == 'N':
            print(f"\nPlease select which categories to filter by (comma-separated):")
            print(f"Available categories: {', '.join(available_categories)}")
            
            while True:
                selected = input().strip()
                if not selected:
                    return None
                
                selected_categories = [cat.strip() for cat in selected.split(',')]
                valid_categories = [cat for cat in selected_categories if cat in available_categories]
                
                if valid_categories:
                    return valid_categories
                else:
                    print("No valid categories selected. Please try again.")
        else:
            print("Please enter Y or N:")

def filter_results_by_categories(results, selected_categories):
    """Filter results by selected categories and group them."""
    if not selected_categories:
        return {'all': results}
    
    grouped_results = {}
    
    for category in selected_categories:
        grouped_results[category] = []
    
    # Add an 'other' category for items that don't match any selected categories
    grouped_results['other'] = []
    
    for result in results:
        item_categories = result.get('categories', [])
        matched_any = False
        
        for category in selected_categories:
            if category in item_categories:
                grouped_results[category].append(result)
                matched_any = True
                break  # Only add to first matching category group
        
        if not matched_any:
            grouped_results['other'].append(result)
    
    # Remove empty groups
    return {k: v for k, v in grouped_results.items() if v}

def normalize_content_name(filename):
    """Normalize content name for duplicate detection."""
    # This function has been removed as it's no longer needed
    return Path(filename).stem.lower()

def analyze_missing_trackers():
    """Main function to analyze missing trackers using client_searchee table."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Step 1: Build comprehensive domain to abbreviation mapping
        domain_to_abbrev, available_trackers = build_comprehensive_tracker_mapping()
        
        if not available_trackers:
            print("No trackers found in database that match TRACKER_MAPPING")
            return [], []
        
        # Step 2: Load configuration with available trackers
        print("\nStep 2: Loading configuration...")
        config = load_config(available_trackers)
        
        # Filter trackers based on config
        enabled_trackers = get_enabled_trackers_from_config(config, available_trackers)
        print(f"Enabled trackers for cross-seeding: {', '.join(enabled_trackers)}")
        
        # Get all torrents with their tracker lists, paths, and categories
        print("\nStep 3: Analyzing torrents and their tracker coverage...")
        cursor.execute("""
            SELECT name, info_hash, save_path, trackers, category
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
            return [], []
        
        print(f"Found {total_torrents} torrents to analyze")
        
        results = []
        content_groups = defaultdict(list)  # Group by normalized name to handle duplicates
        all_categories = set()  # Collect all categories found
        start_time = time.time()
        
        # Check single episode settings
        include_single_episodes = should_include_single_episodes(config)
        print(f"Single episode handling: {'Include' if include_single_episodes else 'Exclude'}")
        
        # Process each torrent
        for i, row in enumerate(torrent_rows):
            print_progress_bar(i + 1, total_torrents, start_time, "Processing torrents")
            
            name, info_hash, save_path, trackers_json, category_data = row
            
            # Only process video files
            if not is_video_file(name):
                continue
            
            # Handle single episode filtering
            if is_single_episode(name, config) and not include_single_episodes:
                continue
            
            # Parse categories
            item_categories = []
            if category_data:
                # Handle both single categories and comma-separated lists
                categories = [cat.strip() for cat in str(category_data).split(',') if cat.strip()]
                item_categories = categories
            
            # Add categories to our collection
            all_categories.update(item_categories)
            
            try:
                # Parse the trackers JSON - these are domain names that need mapping
                current_domains = json.loads(trackers_json)
                
                # Map domains to abbreviations
                found_trackers = set()
                for domain in current_domains:
                    if domain in domain_to_abbrev:
                        found_trackers.add(domain_to_abbrev[domain])
                
                # Get all relevant trackers (filtered by config)
                relevant_trackers = filter_relevant_trackers(enabled_trackers, name, enabled_trackers)
                
                # Find missing trackers (relevant trackers not currently found)
                missing_trackers = sorted(set(relevant_trackers) - found_trackers)
                
                # Always include entries if they have found trackers on relevant trackers OR missing trackers
                found_relevant_trackers = sorted(found_trackers & set(relevant_trackers))
                
                if missing_trackers or found_relevant_trackers:
                    # Simplified grouping without complex normalization
                    normalized_name = normalize_content_name(name)
                    content_groups[normalized_name].append({
                        'name': name,
                        'info_hash': info_hash,
                        'path': save_path,
                        'missing_trackers': missing_trackers,
                        'found_trackers': found_relevant_trackers,
                        'normalized_name': normalized_name,
                        'categories': item_categories
                    })
                    
            except json.JSONDecodeError:
                # Skip torrents with invalid JSON
                continue
        
        print()  # New line after progress bar
        
        # Process content groups and handle duplicates
        print("Step 4: Processing content groups and handling duplicates...")
        processed_content = set()
        
        for normalized_name, items in content_groups.items():
            if normalized_name in processed_content:
                continue
            
            if len(items) > 1:
                # Handle duplicates - merge found trackers and categories, use primary item
                merged_found_trackers = set()
                merged_categories = set()
                for item in items:
                    merged_found_trackers.update(item['found_trackers'])
                    merged_categories.update(item['categories'])
                
                # Use first item as primary and update its found trackers and categories
                primary_item = items[0]
                relevant_trackers = filter_relevant_trackers(enabled_trackers, primary_item['name'], enabled_trackers)
                missing_trackers = sorted(set(relevant_trackers) - merged_found_trackers)
                
                if missing_trackers or merged_found_trackers:
                    primary_item['missing_trackers'] = missing_trackers
                    primary_item['found_trackers'] = sorted(merged_found_trackers & set(relevant_trackers))
                    primary_item['duplicates'] = [item['name'] for item in items]
                    primary_item['categories'] = sorted(merged_categories)
                    results.append(primary_item)
            else:
                # Single item
                if items[0]['missing_trackers'] or items[0]['found_trackers']:
                    results.append(items[0])
            
            processed_content.add(normalized_name)
        
        conn.close()
        return results, sorted(all_categories)
        
    except Exception as e:
        print(f"Error analyzing missing trackers: {e}")
        return [], []

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
                if item.get('categories'):
                    f.write(f"# Categories: {', '.join(item['categories'])}\n")
                f.write(f"# Missing from: {', '.join(item['missing_trackers']) if item['missing_trackers'] else 'None'}\n")
                f.write(f"# Found on: {', '.join(item['found_trackers']) if item['found_trackers'] else 'None'}\n")
            
            # Construct the full file path by combining directory and filename
            base_path = Path(item["path"])
            torrent_name = item["name"]
            full_file_path = base_path / torrent_name
            
            # Create the tracker list parameter - only include missing trackers
            if item['missing_trackers']:
                tracker_list = ','.join(item['missing_trackers'])
                f.write(f'python3 upload.py "{full_file_path}" --trackers {tracker_list}\n')
            else:
                f.write(f'# No missing trackers for: {full_file_path}\n')
            
            if not clean_output:
                f.write('\n')
    
    print()  # New line after progress bar
    print(f"Upload commands written to: {filename}")
    return filename

def debug_tracker_mapping():
    """Debug function to show detailed tracker mapping analysis."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    appdata_dir = Path(LOG_DIR)
    appdata_dir.mkdir(parents=True, exist_ok=True)
    debug_file = appdata_dir / f"tracker_mapping_debug_{timestamp}.txt"
    
    print("Running detailed tracker mapping analysis...")
    
    try:
        # Get unique domains from database
        unique_domains = extract_unique_trackers_from_db()
        domain_to_abbrev, mapped_trackers = build_comprehensive_tracker_mapping()
        
        with open(debug_file, 'w') as f:
            f.write("TRACKER MAPPING ANALYSIS\n")
            f.write("=" * 50 + "\n\n")
            
            f.write(f"Total unique domains in database: {len(unique_domains)}\n")
            f.write(f"Successfully mapped domains: {len(domain_to_abbrev)}\n")
            f.write(f"Unique tracker abbreviations: {len(mapped_trackers)}\n\n")
            
            f.write("DOMAIN TO ABBREVIATION MAPPING:\n")
            f.write("-" * 40 + "\n")
            for domain in sorted(unique_domains):
                abbrev = domain_to_abbrev.get(domain, "UNMAPPED")
                f.write(f"{domain:<35} -> {abbrev}\n")
            
            f.write(f"\nMAPPED TRACKER ABBREVIATIONS ({len(mapped_trackers)}):\n")
            f.write("-" * 40 + "\n")
            for abbrev in sorted(mapped_trackers):
                f.write(f"  {abbrev}\n")
            
            # Show unmapped domains
            unmapped = [d for d in unique_domains if d not in domain_to_abbrev]
            if unmapped:
                f.write(f"\nUNMAPPED DOMAINS ({len(unmapped)}):\n")
                f.write("-" * 40 + "\n")
                for domain in sorted(unmapped):
                    f.write(f"  {domain}\n")
                    
                f.write(f"\nSUGGESTED TRACKER_MAPPING ADDITIONS:\n")
                f.write("-" * 40 + "\n")
                for domain in sorted(unmapped):
                    # Try to guess abbreviation from domain
                    if '.' in domain:
                        potential_abbrev = domain.split('.')[0].upper()
                        f.write(f"    '{potential_abbrev}': ['{potential_abbrev.lower()}', '{domain}'],\n")
        
        print(f"Detailed tracker mapping analysis written to: {debug_file}")
        
    except Exception as e:
        print(f"Error in tracker mapping debug: {e}")

def show_config_info(config):
    """Display current configuration information."""
    print("\nCurrent Configuration:")
    print("=" * 40)
    
    if config.has_section('TRACKERS'):
        enabled = config['TRACKERS'].get('enabled_trackers', '').strip()
        disabled = config['TRACKERS'].get('disabled_trackers', '').strip()
        
        if enabled:
            print(f"Enabled trackers: {enabled}")
        elif disabled:
            print(f"Disabled trackers: {disabled}")
        else:
            print("Tracker filtering: None (all available trackers)")
    
    if config.has_section('FILTERING'):
        include_episodes = config['FILTERING'].getboolean('include_single_episodes', fallback=False)
        exclude_episodes = config['FILTERING'].getboolean('exclude_single_episodes', fallback=True)
        patterns = config['FILTERING'].get('single_episode_patterns', 'S\\d{2}E\\d{2},EP?\\d+,Episode\\s*\\d+')
        
        if exclude_episodes:
            print(f"Single episodes: Excluded")
        elif include_episodes:
            print(f"Single episodes: Included")
        else:
            print(f"Single episodes: Default behavior")
        
        print(f"Episode patterns: {patterns}")
    
    if config.has_section('GENERAL'):
        auto_filter = config['GENERAL'].getboolean('auto_filter_categories', fallback=False)
        default_cats = config['GENERAL'].get('default_categories', 'Movies,TV')
        
        if auto_filter:
            print(f"Auto-filter categories: Enabled ({default_cats})")
        else:
            print(f"Auto-filter categories: Disabled")
    
    print(f"\nConfig file location: {CONFIG_FILE}")
    print("Edit the config file to change these settings.\n")

def main():
    parser = argparse.ArgumentParser(
        description="Cross-Pollinator: Analyze missing torrents using cross-seed database"
    )
    parser.add_argument('--run', action='store_true', help='Run analysis and show missing torrents')
    parser.add_argument('--output', nargs='?', const='default', help='Generate upload commands file (optional filename)')
    parser.add_argument('--no-emoji', action='store_true', help='Remove all emojis from output')
    parser.add_argument('--output-clean', action='store_true', help='Generate clean output with only upload commands')
    parser.add_argument('--debug-trackers', action='store_true', help='Show detailed tracker mapping analysis')
    parser.add_argument('--no-filter', action='store_true', help='Skip category filtering prompt and show all results')
    parser.add_argument('--show-config', action='store_true', help='Display current configuration settings')
    
    args = parser.parse_args()
    
    if args.show_config:
        # Load config without available trackers for display
        config = load_config()
        show_config_info(config)
        if not args.run and not args.debug_trackers:
            return
    
    if not args.run and not args.debug_trackers:
        parser.print_help()
        sys.exit(1)
    
    if not Path(DB_PATH).exists():
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)
    
    # Show debug tracker mapping if requested
    if args.debug_trackers:
        debug_tracker_mapping()
        if not args.run:
            return
        print()
    
    print("Analyzing cross-seed database for missing torrents...")
    results, all_categories = analyze_missing_trackers()
    
    if not results:
        print("No torrents found needing upload to additional trackers")
        return
    
    print(f"Found {len(results)} video files needing upload to additional trackers")
    
    # Handle category filtering unless --no-filter is specified
    selected_categories = None
    grouped_results = {'all': results}
    
    if not args.no_filter and all_categories:
        # Load config for category filtering
        config = load_config()
        selected_categories = prompt_category_filter(all_categories, config)
        if selected_categories:
            grouped_results = filter_results_by_categories(results, selected_categories)
    
    # Display results unless clean output requested
    if not args.output_clean:
        print("\nMissing Video Files by Tracker:")
        print("=" * 80)
        
        for group_name, group_results in grouped_results.items():
            if len(grouped_results) > 1:  # Only show group headers if we have multiple groups
                print(f"\n{'='*20} {group_name.upper()} CONTENT {'='*20}")
                print(f"Found {len(group_results)} items in this category\n")
            
            for item in sorted(group_results, key=lambda x: x['name'].lower()):
                print(f"\n{item['name']}")
                if item.get('duplicates'):
                    print(f"   Duplicates detected: {', '.join(item['duplicates'])}")
                print(f"   Path: {item['path']}")
                if item.get('categories'):
                    print(f"   Categories: {', '.join(item['categories'])}")
                print(f"   Missing from: {', '.join(item['missing_trackers']) if item['missing_trackers'] else 'None'}")
                if item['found_trackers']:
                    print(f"   Found on: {', '.join(item['found_trackers'])}")
                else:
                    print(f"   Found on: None")
    
    # Generate upload commands if requested
    if args.output is not None:
        # Flatten grouped results for command generation
        all_filtered_results = []
        for group_results in grouped_results.values():
            all_filtered_results.extend(group_results)
        
        output_file = args.output if args.output != 'default' else None
        commands_file = generate_upload_commands(all_filtered_results, output_file, args.output_clean)
        if not args.output_clean:
            print(f"\nUpload commands written to: {commands_file}")
            print("Review the file before executing upload commands")
    elif not args.output_clean:
        print("\nUse --output to generate upload commands file")
    
    if not args.output_clean:
        print("\nAnalysis complete!")

if __name__ == "__main__":
    main()
