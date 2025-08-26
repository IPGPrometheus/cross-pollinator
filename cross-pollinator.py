#!/usr/bin/env python3
"""
Cross-Pollinator Uploader - Generate Upload Commands (Improved Tracker Mapping + Folder Support)

Parses cross-seed database using client_searchee table to find missing trackers.
Uses info_hash to match torrents and trackers column to determine missing trackers.
Now supports both individual files and folder structures (seasons, collections, etc.).
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
from bannedgroups import filter_torrents_by_banned_groups, extract_release_group
import asyncio
import re
import time

load_dotenv()

# Configuration
CROSS_SEED_DIR = os.environ.get('CROSS_SEED_DIR', '/cross-seed')
DB_PATH = os.path.join(CROSS_SEED_DIR, 'cross-seed.db')
LOG_DIR = os.environ.get('CROSS_POLLINATOR_LOG_DIR', '/logs')
CONFIG_DIR = os.environ.get('CROSS_POLLINATOR_CONFIG_DIR', 
                           os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config'))
CONFIG_FILE = os.path.join(CONFIG_DIR, 'cross-pollinator-config.txt')

# Video file extensions
VIDEO_EXTENSIONS = {
    '.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v',
    '.mpg', '.mpeg', '.3gp', '.3g2', '.asf', '.rm', '.rmvb', '.vob',
    '.ts', '.mts', '.m2ts', '.divx', '.xvid', '.f4v', '.ogv'
}

# Video patterns for folder detection
VIDEO_PATTERNS = [
    r'S\d{2}',  # Season pattern
    r'\d{4}',   # Year pattern
    r'(1080p|720p|2160p|4K)',  # Resolution patterns
    r'(x264|x265|H\.264|H\.265)',  # Codec patterns
    r'(BluRay|WEB-DL|WEBRip|DVDRip)',  # Source patterns
]

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


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'
    
    @classmethod
    def disable(cls):
        """Disable colors (for clean output or non-terminal environments)."""
        cls.GREEN = cls.YELLOW = cls.RED = cls.BLUE = cls.CYAN = cls.WHITE = cls.BOLD = cls.END = ''


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


def create_default_config(available_trackers=None):
    """Create a default configuration file."""
    config = configparser.ConfigParser()
    
    default_trackers = ','.join(available_trackers) if available_trackers else 'BLU,AITHER,ANT,BHD,MTV,FL,TL,BTN,PHD'
    
    config['TRACKERS'] = {
        'enabled_trackers': default_trackers,
        'disabled_trackers': '',
        'comment': '# Comma-separated list of tracker abbreviations to include/exclude',
        
        # Add API keys for trackers that support banned groups,
        AITHER : {"api_key": "your_aither_api_key_here"},
        LST : {"api_key": "your_lst_api_key_here"}

    }
    
    config['FILTERING'] = {
        'include_single_episodes': 'false',
        'exclude_single_episodes': 'true',
        'single_episode_patterns': r'S\d{2}E\d{2},EP?\d+,Episode\s*\d+,\d{4}[.\-]\d{2}[.\-]\d{2}',
        'include_folders': 'true',
        'prefer_seasons_over_episodes': 'true',
        'filter_banned_groups': 'true',  # NEW
        'comment': '# Set include_single_episodes=true to include single episodes, false to exclude'
    }
    
    config['BANNED_GROUPS'] = {  # NEW SECTION
        'enabled': 'true',
        'check_all_trackers': 'true',
        'cache_duration_hours': '24',
        'verbose_filtering': 'false',
        'comment': '# Banned groups filtering settings'
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
        sections = {
            'TRACKERS': {'enabled_trackers': '', 'disabled_trackers': ''},
            'FILTERING': {
                'include_single_episodes': 'false', 
                'exclude_single_episodes': 'true',
                'include_folders': 'true',
                'prefer_seasons_over_episodes': 'true',
                'filter_banned_groups': 'true'  # NEW
            },
            'BANNED_GROUPS': {  # NEW SECTION
                'enabled': 'true',
                'check_all_trackers': 'true',
                'cache_duration_hours': '24',
                'verbose_filtering': 'false'
            },
            'GENERAL': {'auto_filter_categories': 'false', 'default_categories': 'Movies,TV'}
        }
        
        for section_name, defaults in sections.items():
            if section_name not in config:
                config[section_name] = defaults
    
    return config

def get_enabled_trackers_from_config(config, available_trackers):
    """Get list of enabled trackers based on configuration."""
    enabled_list = config['TRACKERS'].get('enabled_trackers', '').strip()
    disabled_list = config['TRACKERS'].get('disabled_trackers', '').strip()
    
    if enabled_list:
        enabled = [t.strip().upper() for t in enabled_list.split(',') if t.strip()]
        result = [t for t in enabled if t in available_trackers]
        print(f"Using enabled trackers from config: {', '.join(result)}")
        return result
    elif disabled_list:
        disabled = [t.strip().upper() for t in disabled_list.split(',') if t.strip()]
        result = [t for t in available_trackers if t not in disabled]
        print(f"Excluding disabled trackers from config: {', '.join(disabled)}")
        print(f"Remaining trackers: {', '.join(result)}")
        return result
    else:
        print("No tracker filtering specified in config, using all available trackers")
        return available_trackers


def is_single_episode(filename, config):
    """Check if filename appears to be a single episode based on config patterns."""
    patterns = config['FILTERING'].get('single_episode_patterns', 
                                      r'S\d{2}E\d{2},EP?\d+,Episode\s*\d+,\d{4}[.\-]\d{2}[.\-]\d{2}').split(',')
    filename_lower = filename.lower()
    
    for pattern in patterns:
        pattern = pattern.strip()
        if pattern and re.search(pattern, filename_lower, re.IGNORECASE):
            return True
    
    return False


def get_config_bool(config, section, key, default=False):
    """Get boolean value from config with fallback."""
    return config[section].getboolean(key, fallback=default)


def is_season_from_files(files_json):
    """Check if the torrent represents a season based on files structure."""
    if not files_json:
        return False, 0
    
    try:
        files = json.loads(files_json)
        if not isinstance(files, list) or len(files) <= 1:
            return False, 0
        
        episode_count = 0
        season_pattern = re.compile(r'S\d{2}E\d{2}', re.IGNORECASE)
        
        for file_info in files:
            if isinstance(file_info, dict) and 'name' in file_info:
                filename = file_info['name']
                if season_pattern.search(filename):
                    episode_count += 1
        
        return (episode_count > 1, episode_count)
            
    except (json.JSONDecodeError, TypeError):
        return False, 0


def is_video_content(name, files_json=None):
    """Check if content is video-related (file or folder with video files)."""
    # First check if it's a season from files
    is_season, _ = is_season_from_files(files_json)
    if is_season:
        return True
    
    # Check if single file has video extension
    if Path(name).suffix.lower() in VIDEO_EXTENSIONS:
        return True
    
    # If we have files JSON, check if any files are video files
    if files_json:
        try:
            files = json.loads(files_json)
            if isinstance(files, list):
                for file_info in files:
                    if isinstance(file_info, dict) and 'name' in file_info:
                        filename = file_info['name']
                        if Path(filename).suffix.lower() in VIDEO_EXTENSIONS:
                            return True
        except (json.JSONDecodeError, TypeError):
            pass
    
    # Check for common video-related patterns in folder names
    name_lower = name.lower()
    for pattern in VIDEO_PATTERNS:
        if re.search(pattern, name_lower, re.IGNORECASE):
            return True
    
    return False


def extract_unique_items_from_db(column, table='client_searchee', where_clause=None):
    """Generic function to extract unique items from database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        base_query = f"""
            SELECT DISTINCT {column}
            FROM {table}
            WHERE {column} IS NOT NULL 
            AND {column} != ''
            AND {column} != 'null'
        """
        
        if where_clause:
            base_query += f" AND {where_clause}"
        
        cursor.execute(base_query)
        rows = cursor.fetchall()
        conn.close()
        
        return [row[0] for row in rows if row[0]]
        
    except Exception as e:
        print(f"Error extracting unique {column}: {e}")
        return []


def extract_unique_trackers_from_db():
    """Extract all unique tracker domains from the database."""
    print("Extracting unique trackers from database...")
    
    trackers_data = extract_unique_items_from_db('trackers', where_clause="trackers != '[]'")
    unique_domains = set()
    
    for trackers_json in trackers_data:
        try:
            trackers_list = json.loads(trackers_json)
            for domain in trackers_list:
                if domain and isinstance(domain, str):
                    unique_domains.add(domain.strip())
        except json.JSONDecodeError:
            continue
    
    return sorted(unique_domains)


def extract_unique_categories_from_db():
    """Extract all unique categories from the database."""
    print("Extracting all unique categories from database...")
    
    category_data = extract_unique_items_from_db('category')
    unique_categories = set()
    
    for category in category_data:
        category_str = str(category).strip()
        
        # Split by multiple possible separators
        separators = [',', ';', '|', '/']
        categories = [category_str]
        
        for sep in separators:
            new_categories = []
            for cat in categories:
                new_categories.extend([c.strip() for c in cat.split(sep) if c.strip()])
            categories = new_categories
        
        # Clean and add categories
        for cat in categories:
            cleaned_cat = cat.strip().strip('\'"[]{}()')
            if cleaned_cat and cleaned_cat.lower() not in ['null', 'none', '']:
                unique_categories.add(cleaned_cat)
    
    result = sorted(unique_categories)
    print(f"Found {len(result)} unique categories in database: {', '.join(result)}")
    return result


def map_domain_to_abbreviation(domain):
    """Map a tracker domain to its abbreviation using TRACKER_MAPPING with improved matching."""
    if not domain:
        return None
    
    domain_lower = domain.lower().strip()
    
    # Create a list of (abbrev, variant) tuples sorted by variant length (longest first)
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
    
    unique_domains = extract_unique_trackers_from_db()
    print(f"Found {len(unique_domains)} unique tracker domains in database")
    
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


def parse_categories(category_data):
    """Parse category data into a list of cleaned categories."""
    if not category_data:
        return []
    
    raw_categories = str(category_data).split(',')
    return [cat.strip() for cat in raw_categories if cat.strip()]


def normalize_content_name(filename):
    """Normalize content name for duplicate detection."""
    normalized = (Path(filename).stem + Path(filename).suffix).lower()
    normalized = re.sub(r'[.\-_]', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def create_torrent_item(row, domain_to_abbrev, enabled_trackers, config):
    """Create torrent item data structure from database row."""
    name, info_hash, save_path, trackers_json, category_data, files_json = row
    
    # Check if content is video-related
    if not is_video_content(name, files_json):
        return None
    
    # Check season info
    is_season, episode_count = is_season_from_files(files_json)
    
    # Handle single episode filtering
    if is_single_episode(name, config) and not get_config_bool(config, 'FILTERING', 'include_single_episodes'):
        return None
    
    # Handle folder filtering
    if not is_season and not Path(name).suffix and not get_config_bool(config, 'FILTERING', 'include_folders', True):
        return None
    
    # Parse categories
    item_categories = parse_categories(category_data)
    
    try:
        # Parse and map trackers
        current_domains = json.loads(trackers_json)
        found_trackers = {domain_to_abbrev[domain] for domain in current_domains 
                         if domain in domain_to_abbrev}
        
        # Find missing trackers
        relevant_trackers = set(enabled_trackers)
        missing_trackers = sorted(relevant_trackers - found_trackers)
        found_relevant_trackers = sorted(found_trackers & relevant_trackers)
        
        if missing_trackers or found_relevant_trackers:
            return {
                'name': name,
                'info_hash': info_hash,
                'path': save_path,
                'missing_trackers': missing_trackers,
                'found_trackers': found_relevant_trackers,
                'categories': item_categories,
                'is_season': is_season,
                'episode_count': episode_count,
                'files_json': files_json
            }
    
    except json.JSONDecodeError:
        pass
    
    return None


def process_season_episode_preferences(season_episode_groups, content_groups, enabled_trackers):
    """Process season/episode groups with preference handling."""
    print("Step 4: Processing season/episode preferences...")
    
    for normalized_name, items in season_episode_groups.items():
        seasons = [item for item in items if item['is_season']]
        episodes = [item for item in items if not item['is_season']]
        
        if seasons:
            # Merge episode data into seasons
            for season in seasons:
                merged_found_trackers = set(season['found_trackers'])
                merged_categories = set(season['categories'])
                
                for episode in episodes:
                    merged_found_trackers.update(episode['found_trackers'])
                    merged_categories.update(episode['categories'])
                
                # Update season with merged data
                missing_trackers = sorted(set(enabled_trackers) - merged_found_trackers)
                season['missing_trackers'] = missing_trackers
                season['found_trackers'] = sorted(merged_found_trackers & set(enabled_trackers))
                season['categories'] = sorted(merged_categories)
                
                if episodes:
                    season['consolidated_episodes'] = [ep['name'] for ep in episodes]
                
                content_groups[normalized_name].append(season)
        else:
            content_groups[normalized_name].extend(episodes)


def process_content_groups(content_groups, enabled_trackers):
    """Process content groups and handle duplicates."""
    print("Step 5: Processing content groups and handling duplicates...")
    
    results = []
    processed_content = set()
    
    for normalized_name, items in content_groups.items():
        if normalized_name in processed_content:
            continue
        
        if len(items) > 1:
            # Handle duplicates
            merged_found_trackers = set()
            merged_categories = set()
            
            for item in items:
                merged_found_trackers.update(item['found_trackers'])
                merged_categories.update(item['categories'])
            
            # Use first item as primary
            primary_item = items[0]
            missing_trackers = sorted(set(enabled_trackers) - merged_found_trackers)
            
            if missing_trackers or merged_found_trackers:
                primary_item['missing_trackers'] = missing_trackers
                primary_item['found_trackers'] = sorted(merged_found_trackers & set(enabled_trackers))
                primary_item['duplicates'] = [item['name'] for item in items]
                primary_item['categories'] = sorted(merged_categories)
                results.append(primary_item)
        else:
            if items[0]['missing_trackers'] or items[0]['found_trackers']:
                results.append(items[0])
        
        processed_content.add(normalized_name)
    
    return results


async def analyze_missing_trackers():
    """Main function to analyze missing trackers using client_searchee table."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Step 1: Build comprehensive domain to abbreviation mapping
        domain_to_abbrev, available_trackers = build_comprehensive_tracker_mapping()
        
        if not available_trackers:
            print("No trackers found in database that match TRACKER_MAPPING")
            return [], []
        
        # Step 2: Load configuration
        print("\nStep 2: Loading configuration...")
        config = load_config(available_trackers)
        enabled_trackers = get_enabled_trackers_from_config(config, available_trackers)
        print(f"Enabled trackers for cross-seeding: {', '.join(enabled_trackers)}")
        
        # Check if banned groups filtering is enabled
        banned_groups_enabled = get_config_bool(config, 'BANNED_GROUPS', 'enabled', True)
        banned_groups_verbose = get_config_bool(config, 'BANNED_GROUPS', 'verbose_filtering', False)
        
        if banned_groups_enabled:
            print(f"Banned groups filtering: Enabled (verbose: {banned_groups_verbose})")
        
        # Step 3: Query torrents
        print("\nStep 3: Analyzing torrents and their tracker coverage...")
        cursor.execute("""
            SELECT name, info_hash, save_path, trackers, category, files
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
        
        # Display configuration
        include_single_episodes = get_config_bool(config, 'FILTERING', 'include_single_episodes')
        include_folders = get_config_bool(config, 'FILTERING', 'include_folders', True)
        prefer_seasons = get_config_bool(config, 'FILTERING', 'prefer_seasons_over_episodes', True)
        
        print(f"Configuration - Single episodes: {'Include' if include_single_episodes else 'Exclude'}")
        print(f"Configuration - Folders: {'Include' if include_folders else 'Exclude'}")
        print(f"Configuration - Prefer seasons over episodes: {'Yes' if prefer_seasons else 'No'}")
        
        # Process torrents
        content_groups = defaultdict(list)
        season_episode_groups = defaultdict(list) if prefer_seasons else None
        all_categories = set()
        start_time = time.time()
        
        for i, row in enumerate(torrent_rows):
            print_progress_bar(i + 1, total_torrents, start_time, "Processing torrents")
            
            item_data = create_torrent_item(row, domain_to_abbrev, enabled_trackers, config)
            if not item_data:
                continue
            
            # Collect categories
            all_categories.update(item_data['categories'])
            
            # Group items based on preference
            normalized_name = normalize_content_name(item_data['name'])
            
            if prefer_seasons and (item_data['is_season'] or is_single_episode(item_data['name'], config)):
                season_episode_groups[normalized_name].append(item_data)
            else:
                content_groups[normalized_name].append(item_data)
        
        print()  # New line after progress bar
        
        # Process groups
        if prefer_seasons and season_episode_groups:
            process_season_episode_preferences(season_episode_groups, content_groups, enabled_trackers)
        
        results = process_content_groups(content_groups, enabled_trackers)
        
        # NEW: Apply banned groups filtering
        if banned_groups_enabled and results:
            print(f"\nStep 6: Filtering banned release groups...")
            
            # Get base directory for banned groups data
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Create config dict in the format expected by bannedgroups module
            banned_groups_config = {}
            if config.has_section('TRACKERS'):
                banned_groups_config['TRACKERS'] = dict(config['TRACKERS'])
            
            try:
                # Filter results using banned groups
                filtered_results, banned_torrents, filtering_stats = await filter_torrents_by_banned_groups(
                    results, enabled_trackers, banned_groups_config, base_dir, banned_groups_verbose
                )
                
                if filtering_stats['banned_count'] > 0:
                    print(f"Filtered out {filtering_stats['banned_count']} torrents with banned release groups")
                    
                    if banned_groups_verbose:
                        print(f"Banned groups breakdown:")
                        for tracker, count in filtering_stats['by_tracker'].items():
                            if count > 0:
                                print(f"  {tracker}: {count} torrents")
                
                results = filtered_results
                
            except ImportError:
                print("Warning: bannedgroups module not found, skipping banned groups filtering")
            except Exception as e:
                print(f"Warning: Error during banned groups filtering: {e}")
        
        conn.close()
        return results, sorted(all_categories)
        
    except Exception as e:
        print(f"Error analyzing missing trackers: {e}")
        return [], []


# ADD this NEW function after the analyze_missing_trackers() function:
def analyze_missing_trackers_sync():
    """Synchronous fallback version without banned groups filtering."""
    print("Running synchronous analysis (banned groups filtering disabled)")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Step 1: Build comprehensive domain to abbreviation mapping
        domain_to_abbrev, available_trackers = build_comprehensive_tracker_mapping()
        
        if not available_trackers:
            print("No trackers found in database that match TRACKER_MAPPING")
            return [], []
        
        # Step 2: Load configuration
        print("\nStep 2: Loading configuration...")
        config = load_config(available_trackers)
        enabled_trackers = get_enabled_trackers_from_config(config, available_trackers)
        print(f"Enabled trackers for cross-seeding: {', '.join(enabled_trackers)}")
        print("Note: Banned groups filtering disabled in sync mode")
        
        # Step 3: Query torrents
        print("\nStep 3: Analyzing torrents and their tracker coverage...")
        cursor.execute("""
            SELECT name, info_hash, save_path, trackers, category, files
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
        
        # Display configuration
        include_single_episodes = get_config_bool(config, 'FILTERING', 'include_single_episodes')
        include_folders = get_config_bool(config, 'FILTERING', 'include_folders', True)
        prefer_seasons = get_config_bool(config, 'FILTERING', 'prefer_seasons_over_episodes', True)
        
        print(f"Configuration - Single episodes: {'Include' if include_single_episodes else 'Exclude'}")
        print(f"Configuration - Folders: {'Include' if include_folders else 'Exclude'}")
        print(f"Configuration - Prefer seasons over episodes: {'Yes' if prefer_seasons else 'No'}")
        
        # Process torrents (same as async version but without banned groups filtering)
        content_groups = defaultdict(list)
        season_episode_groups = defaultdict(list) if prefer_seasons else None
        all_categories = set()
        start_time = time.time()
        
        for i, row in enumerate(torrent_rows):
            print_progress_bar(i + 1, total_torrents, start_time, "Processing torrents")
            
            item_data = create_torrent_item(row, domain_to_abbrev, enabled_trackers, config)
            if not item_data:
                continue
            
            # Collect categories
            all_categories.update(item_data['categories'])
            
            # Group items based on preference
            normalized_name = normalize_content_name(item_data['name'])
            
            if prefer_seasons and (item_data['is_season'] or is_single_episode(item_data['name'], config)):
                season_episode_groups[normalized_name].append(item_data)
            else:
                content_groups[normalized_name].append(item_data)
        
        print()  # New line after progress bar
        
        # Process groups
        if prefer_seasons and season_episode_groups:
            process_season_episode_preferences(season_episode_groups, content_groups, enabled_trackers)
        
        results = process_content_groups(content_groups, enabled_trackers)
        
        conn.close()
        return results, sorted(all_categories)
        
    except Exception as e:
        print(f"Error analyzing missing trackers: {e}")
        return [], []

async def analyze_missing_trackers_async(args):
    """Async wrapper for analyze_missing_trackers with banned groups filtering."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Step 1: Build comprehensive domain to abbreviation mapping
        domain_to_abbrev, available_trackers = build_comprehensive_tracker_mapping()
        
        if not available_trackers:
            print("No trackers found in database that match TRACKER_MAPPING")
            return [], []
        
        # Step 2: Load configuration
        print("\nStep 2: Loading configuration...")
        config = load_config(available_trackers)
        enabled_trackers = get_enabled_trackers_from_config(config, available_trackers)
        print(f"Enabled trackers for cross-seeding: {', '.join(enabled_trackers)}")
        
        # Check if banned groups filtering is enabled
        banned_groups_enabled = (
            get_config_bool(config, 'BANNED_GROUPS', 'enabled', True) and 
            not args.no_banned_filter
        )
        banned_groups_verbose = get_config_bool(config, 'BANNED_GROUPS', 'verbose_filtering', False)
        
        if banned_groups_enabled:
            print(f"Banned groups filtering: Enabled (verbose: {banned_groups_verbose})")
        elif args.no_banned_filter:
            print("Banned groups filtering: Disabled by --no-banned-filter")
        
        # Step 3: Query torrents (same as before)
        print("\nStep 3: Analyzing torrents and their tracker coverage...")
        cursor.execute("""
            SELECT name, info_hash, save_path, trackers, category, files
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
        
        # Display configuration
        include_single_episodes = get_config_bool(config, 'FILTERING', 'include_single_episodes')
        include_folders = get_config_bool(config, 'FILTERING', 'include_folders', True)
        prefer_seasons = get_config_bool(config, 'FILTERING', 'prefer_seasons_over_episodes', True)
        
        print(f"Configuration - Single episodes: {'Include' if include_single_episodes else 'Exclude'}")
        print(f"Configuration - Folders: {'Include' if include_folders else 'Exclude'}")
        print(f"Configuration - Prefer seasons over episodes: {'Yes' if prefer_seasons else 'No'}")
        
        # Process torrents (same as before)
        content_groups = defaultdict(list)
        season_episode_groups = defaultdict(list) if prefer_seasons else None
        all_categories = set()
        start_time = time.time()
        
        for i, row in enumerate(torrent_rows):
            print_progress_bar(i + 1, total_torrents, start_time, "Processing torrents")
            
            item_data = create_torrent_item(row, domain_to_abbrev, enabled_trackers, config)
            if not item_data:
                continue
            
            all_categories.update(item_data['categories'])
            normalized_name = normalize_content_name(item_data['name'])
            
            if prefer_seasons and (item_data['is_season'] or is_single_episode(item_data['name'], config)):
                season_episode_groups[normalized_name].append(item_data)
            else:
                content_groups[normalized_name].append(item_data)
        
        print()  # New line after progress bar
        
        # Process groups (same as before)
        if prefer_seasons and season_episode_groups:
            process_season_episode_preferences(season_episode_groups, content_groups, enabled_trackers)
        
        results = process_content_groups(content_groups, enabled_trackers)
        
        # NEW: Apply banned groups filtering
        if banned_groups_enabled and results:
            print(f"\nStep 6: Filtering banned release groups...")
            
            # Get base directory for banned groups data
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Create config dict in the format expected by bannedgroups module
            banned_groups_config = {}
            if config.has_section('TRACKERS'):
                banned_groups_config['TRACKERS'] = dict(config['TRACKERS'])
            
            try:
                from bannedgroups import filter_torrents_by_banned_groups
                
                # Filter results using banned groups
                filtered_results, banned_torrents, filtering_stats = await filter_torrents_by_banned_groups(
                    results, enabled_trackers, banned_groups_config, base_dir, banned_groups_verbose
                )
                
                if filtering_stats['banned_count'] > 0:
                    print(f"Filtered out {filtering_stats['banned_count']} torrents with banned release groups")
                    
                    if banned_groups_verbose:
                        print(f"Banned groups breakdown:")
                        for tracker, count in filtering_stats['by_tracker'].items():
                            if count > 0:
                                print(f"  {tracker}: {count} torrents")
                
                results = filtered_results
                
            except ImportError:
                print("Warning: bannedgroups module not found, skipping banned groups filtering")
            except Exception as e:
                print(f"Warning: Error during banned groups filtering: {e}")
        
        conn.close()
        return results, sorted(all_categories)
        
    except Exception as e:
        print(f"Error analyzing missing trackers: {e}")
        return [], []

def prompt_category_filter(available_categories, config):
    """Prompt user to select which categories to filter by."""
    if not available_categories:
        return None
    
    # Check if auto-filtering is enabled
    if get_config_bool(config, 'GENERAL', 'auto_filter_categories'):
        default_cats = config['GENERAL'].get('default_categories', 'Movies,TV').split(',')
        default_cats = [cat.strip() for cat in default_cats if cat.strip()]
        valid_defaults = [cat for cat in default_cats if cat in available_categories]
        if valid_defaults:
            print(f"Auto-filtering enabled. Using categories: {', '.join(valid_defaults)}")
            return valid_defaults
    
    print(f"\nFound categories: {', '.join(available_categories)}")
    print("\nDo you want to filter by specific categories? (Y/N)")
    print("Y = Select specific categories to show")
    print("N = Show all categories")
    
    while True:
        choice = input().strip().upper()
        if choice == 'Y':
            print(f"\nPlease select which categories to show (comma-separated):")
            print(f"Available categories: {', '.join(available_categories)}")
            
            while True:
                selected = input().strip()
                if not selected:
                    return None
                
                selected_categories = [cat.strip() for cat in selected.split(',')]
                valid_categories = []
                
                # Case-insensitive matching
                for selected_cat in selected_categories:
                    for available_cat in available_categories:
                        if selected_cat.lower() == available_cat.lower():
                            valid_categories.append(available_cat)
                            break
                
                if valid_categories:
                    return valid_categories
                else:
                    print("No valid categories selected. Please try again.")
                    print(f"Available categories: {', '.join(available_categories)}")
        elif choice == 'N':
            return None
        else:
            print("Please enter Y or N:")


def filter_results_by_categories(results, selected_categories):
    """Filter results by selected categories and group them."""
    if not selected_categories:
        return {'all': results}
    
    matching_results = []
    
    for result in results:
        item_categories = result.get('categories', [])
        
        # Check if any item category matches any selected category
        for selected_cat in selected_categories:
            if any(selected_cat.lower().strip() == item_cat.lower().strip() 
                   for item_cat in item_categories):
                matching_results.append(result)
                break
    
    if not matching_results:
        print(f"No results found matching selected categories: {', '.join(selected_categories)}")
        # Show examples of available categories
        example_cats = set()
        for item in results[:10]:
            example_cats.update(item.get('categories', []))
        if example_cats:
            print(f"Available categories in results: {', '.join(sorted(example_cats))}")
        return {}
    
    return {'filtered': matching_results}


def generate_upload_commands(results, output_file=None, clean_output=False):
    """Generate upload.py commands and save them to persistent appdata."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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
            f.write(f"# Total files/folders needing upload: {len(results)}\n\n")
        
        for i, item in enumerate(sorted(results, key=lambda x: x['name'].lower())):
            print_progress_bar(i + 1, len(results), start_time, "Writing commands")
            
            if not clean_output:
                f.write(f"# {item['name']}\n")
                
                if item.get('is_season') and item.get('episode_count'):
                    f.write(f"# Season with {item['episode_count']} episodes\n")
                
                if item.get('consolidated_episodes'):
                    f.write(f"# Consolidated episodes: {', '.join(item['consolidated_episodes'])}\n")
                
                if item.get('duplicates'):
                    f.write(f"# Duplicates: {', '.join(item['duplicates'])}\n")
                
                if item.get('categories'):
                    f.write(f"# Categories: {', '.join(item['categories'])}\n")
                
                f.write(f"# Missing from: {', '.join(item['missing_trackers']) if item['missing_trackers'] else 'None'}\n")
                f.write(f"# Found on: {', '.join(item['found_trackers']) if item['found_trackers'] else 'None'}\n")
            
            # Construct full file path
            base_path = Path(item["path"])
            torrent_name = item["name"]
            full_file_path = base_path / torrent_name
            
            # Create upload command
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
        include_episodes = get_config_bool(config, 'FILTERING', 'include_single_episodes')
        exclude_episodes = get_config_bool(config, 'FILTERING', 'exclude_single_episodes', True)
        include_folders = get_config_bool(config, 'FILTERING', 'include_folders', True)
        prefer_seasons = get_config_bool(config, 'FILTERING', 'prefer_seasons_over_episodes', True)
        filter_banned = get_config_bool(config, 'FILTERING', 'filter_banned_groups', True)  # NEW
        patterns = config['FILTERING'].get('single_episode_patterns', r'S\d{2}E\d{2},EP?\d+,Episode\s*\d+')
        
        if exclude_episodes:
            print(f"Single episodes: Excluded")
        elif include_episodes:
            print(f"Single episodes: Included")
        else:
            print(f"Single episodes: Default behavior")
        
        print(f"Include folders: {'Yes' if include_folders else 'No'}")
        print(f"Prefer seasons over episodes: {'Yes' if prefer_seasons else 'No'}")
        print(f"Filter banned groups: {'Yes' if filter_banned else 'No'}")  # NEW
        print(f"Episode patterns: {patterns}")
    
    # NEW: Display banned groups configuration
    if config.has_section('BANNED_GROUPS'):
        enabled = get_config_bool(config, 'BANNED_GROUPS', 'enabled', True)
        check_all = get_config_bool(config, 'BANNED_GROUPS', 'check_all_trackers', True)
        cache_hours = config['BANNED_GROUPS'].get('cache_duration_hours', '24')
        verbose = get_config_bool(config, 'BANNED_GROUPS', 'verbose_filtering', False)
        
        print(f"\nBanned Groups Settings:")
        print(f"Filtering enabled: {'Yes' if enabled else 'No'}")
        print(f"Check all trackers: {'Yes' if check_all else 'No'}")
        print(f"Cache duration: {cache_hours} hours")
        print(f"Verbose output: {'Yes' if verbose else 'No'}")
    
    if config.has_section('GENERAL'):
        auto_filter = get_config_bool(config, 'GENERAL', 'auto_filter_categories')
        default_cats = config['GENERAL'].get('default_categories', 'Movies,TV')
        
        if auto_filter:
            print(f"Auto-filter categories: Enabled ({default_cats})")
        else:
            print(f"Auto-filter categories: Disabled")
    
    print(f"\nConfig file location: {CONFIG_FILE}")
    print("Edit the config file to change these settings.\n")

def display_results(grouped_results, selected_categories, total_results, args):
    """Display analysis results with proper formatting."""
    print(f"\n{Colors.BOLD}Missing Video Content by Tracker:{Colors.END}")
    print("=" * 80)
    
    # Show filtering info if categories were selected
    if selected_categories:
        print(f"{Colors.CYAN}Filtering by categories: {', '.join(selected_categories)}{Colors.END}")
        total_filtered = sum(len(group) for group in grouped_results.values())
        print(f"{Colors.WHITE}Showing {total_filtered} of {total_results} total results{Colors.END}")
    
    for group_name, group_results in grouped_results.items():
        if selected_categories:
            print(f"\n{Colors.CYAN}{'='*20} FILTERED RESULTS {'='*20}{Colors.END}")
            print(f"{Colors.WHITE}Found {len(group_results)} items matching selected categories{Colors.END}\n")
        
        for item in sorted(group_results, key=lambda x: x['name'].lower()):
            # Torrent name
            print(f"\n{Colors.GREEN}{Colors.BOLD}{item['name']}{Colors.END}")
            
            # Show type information
            if item.get('is_season') and item.get('episode_count'):
                print(f"   {Colors.WHITE}Type: Season ({item['episode_count']} episodes){Colors.END}")
            elif item.get('is_season'):
                print(f"   {Colors.WHITE}Type: Season{Colors.END}")
            elif Path(item['name']).suffix:
                print(f"   {Colors.WHITE}Type: Single file{Colors.END}")
            else:
                print(f"   {Colors.WHITE}Type: Folder{Colors.END}")
            
            # Verbose output
            if args.verbose:
                if item.get('consolidated_episodes'):
                    print(f"   {Colors.BLUE}Consolidated episodes: {', '.join(item['consolidated_episodes'])}{Colors.END}")
                
                if item.get('duplicates'):
                    print(f"   {Colors.BLUE}Duplicates detected: {', '.join(item['duplicates'])}{Colors.END}")
            
            print(f"   {Colors.WHITE}Path: {item['path']}{Colors.END}")
            
            if item.get('categories'):
                print(f"   {Colors.WHITE}Categories: {', '.join(item['categories'])}{Colors.END}")
                
            # Tracker information
            if item['missing_trackers']:
                print(f"   {Colors.RED}Missing from: {', '.join(item['missing_trackers'])}{Colors.END}")
            else:
                print(f"   {Colors.WHITE}Missing from: None{Colors.END}")
            
            if item['found_trackers']:
                print(f"   {Colors.YELLOW}Found on: {', '.join(item['found_trackers'])}{Colors.END}")
            else:
                print(f"   {Colors.WHITE}Found on: None{Colors.END}")

def main():
    parser = argparse.ArgumentParser(
        description="Cross-Pollinator: Analyze missing torrents using cross-seed database (with folder support)"
    )
    parser.add_argument('--run', action='store_true', help='Run analysis and show missing torrents')
    parser.add_argument('--output', nargs='?', const='default', help='Generate upload commands file (optional filename)')
    parser.add_argument('--clean', action='store_true', help='Generate clean output with only upload commands (no colors, no comments)')
    parser.add_argument('--debug-trackers', action='store_true', help='Show detailed tracker mapping analysis')
    parser.add_argument('--no-filter', action='store_true', help='Skip category filtering prompt and show all results')
    parser.add_argument('--show-config', action='store_true', help='Display current configuration settings')
    parser.add_argument('--verbose', action='store_true', help='Show detailed output including duplicates and consolidated episodes')
    parser.add_argument('--no-banned-filter', action='store_true', help='Skip banned groups filtering even if enabled in config')  # NEW
    parser.add_argument('--test-release-group', type=str, help='Test release group extraction on a torrent name')  # NEW
    parser.add_argument('--sync', action='store_true', help='Force synchronous mode (disables banned groups filtering)')  # NEW
    
    args = parser.parse_args()
    
    # NEW: Test release group extraction
    if args.test_release_group:
        try:
            group = extract_release_group(args.test_release_group)
            print(f"Torrent name: {args.test_release_group}")
            print(f"Extracted group: {group if group else 'None detected'}")
        except ImportError:
            print("Error: bannedgroups module not found")
        return
    
    # Disable colors for clean output
    if args.clean:
        Colors.disable()
    
    if args.show_config:
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
    
    # Debug tracker mapping if requested
    if args.debug_trackers:
        debug_tracker_mapping()
        if not args.run:
            return
        print()
    
    print("Analyzing cross-seed database for missing torrents (including folders/seasons)...")
    
    # NEW: Handle async vs sync execution
    if args.sync:
        print("Running in synchronous mode (banned groups filtering disabled)")
        results, all_categories = analyze_missing_trackers_sync()
    else:
        try:
            # Try async first (with banned groups filtering)
            results, all_categories = asyncio.run(analyze_missing_trackers())
        except Exception as e:
            print(f"Async analysis failed ({e}), falling back to synchronous mode")
            results, all_categories = analyze_missing_trackers_sync()
    
    # Get all categories from database for filtering options
    all_db_categories = extract_unique_categories_from_db()
    
    if not results:
        print("No torrents found needing upload to additional trackers")
        return
    
    print(f"Found {len(results)} video files/folders needing upload to additional trackers")
    
    # Handle category filtering
    selected_categories = None
    grouped_results = {'all': results}
    
    if not args.no_filter and all_db_categories:
        config = load_config()
        selected_categories = prompt_category_filter(all_db_categories, config)
        if selected_categories:
            grouped_results = filter_results_by_categories(results, selected_categories)
            
            if not grouped_results:
                print("No matching results to display.")
                return
    
    # Display results unless clean output requested
    if not args.clean:
        display_results(grouped_results, selected_categories, len(results), args)
    
    # Generate upload commands if requested
    if args.output is not None:
        all_filtered_results = []
        for group_results in grouped_results.values():
            all_filtered_results.extend(group_results)
        
        output_file = args.output if args.output != 'default' else None
        commands_file = generate_upload_commands(all_filtered_results, output_file, args.clean)
        if not args.clean:
            print(f"\nUpload commands written to: {commands_file}")
            print("Review the file before executing upload commands")
    elif not args.clean:
        print("\nUse --output to generate upload commands file")
    
    if not args.clean:
        print("\nAnalysis complete!")


if __name__ == "__main__":
    main()
