#!/usr/bin/env python3
"""
Cross-Pollinator Uploader - Generate Upload Commands (Cleaned & Simplified)
Parses cross-seed database to find missing trackers and generates upload commands.
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

# Comprehensive tracker mapping
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
        """Disable colors for clean output."""
        cls.GREEN = cls.YELLOW = cls.RED = cls.BLUE = cls.CYAN = cls.WHITE = cls.BOLD = cls.END = ''

def print_progress_bar(current, total, start_time, prefix="Progress", length=50):
    """Print a progress bar with ETA."""
    if total == 0:
        return
    
    percent = current / total
    filled_length = int(length * percent)
    bar = '█' * filled_length + '-' * (length - filled_length)
    
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
    }
    
    config['FILTERING'] = {
        'include_single_episodes': 'false',
        'include_folders': 'true',
        'prefer_seasons_over_episodes': 'true',
        'filter_banned_groups': 'true',
        'single_episode_patterns': r'S\d{2}E\d{2},EP?\d+,Episode\s*\d+,\d{4}[.\-]\d{2}[.\-]\d{2}',
    }
    
    config['BANNED_GROUPS'] = {
        'enabled': 'true',
        'verbose_filtering': 'false',
        'cache_duration_hours': '24',
    }
    
    config['PERSONAL_FILTERS'] = {
        'enabled': 'false',
        'format_include': '',
        'format_exclude': '',
        'resolution_include': '',
        'resolution_exclude': '480',
        'audio_include': '',
        'audio_exclude': '',
        'channels_include': '',
        'channels_exclude': '2.0',
        'special_flags_include': '',
        'special_flags_exclude': '',
        'filter_mode': 'exclude',
        'case_sensitive': 'false'
    }
    
    config['GENERAL'] = {
        'auto_filter_categories': 'false',
        'default_categories': 'Movies,TV',
    }
    
    return config

def load_config(available_trackers=None):
    """Load configuration from file, create default if doesn't exist."""
    config_path = Path(CONFIG_FILE)
    config = configparser.ConfigParser()
    
    if not config_path.exists():
        print(f"Creating default config at: {CONFIG_FILE}")
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        default_config = create_default_config(available_trackers)
        with open(config_path, 'w') as f:
            default_config.write(f)
        config = default_config
    else:
        config.read(config_path)
    
    return config

def get_config_bool(config, section, key, default=False):
    """Get boolean value from config with fallback."""
    return config[section].getboolean(key, fallback=default)

def get_enabled_trackers_from_config(config, available_trackers):
    """Get list of enabled trackers based on configuration."""
    enabled_list = config['TRACKERS'].get('enabled_trackers', '').strip()
    disabled_list = config['TRACKERS'].get('disabled_trackers', '').strip()
    
    if enabled_list:
        enabled = [t.strip().upper() for t in enabled_list.split(',') if t.strip()]
        result = [t for t in enabled if t in available_trackers]
        print(f"Using enabled trackers: {', '.join(result)}")
        return result
    elif disabled_list:
        disabled = [t.strip().upper() for t in disabled_list.split(',') if t.strip()]
        result = [t for t in available_trackers if t not in disabled]
        print(f"Using all trackers except: {', '.join(disabled)}")
        return result
    else:
        return available_trackers

def fix_config_parsing(config):
    """Parse banned groups configuration."""
    banned_groups_config = {'TRACKERS': {}}
    
    if config.has_section('TRACKERS'):
        for key, value in config['TRACKERS'].items():
            if key in ['enabled_trackers', 'disabled_trackers']:
                continue
            
            key_upper = key.upper()
            
            if value.strip().startswith('{'):
                try:
                    parsed_config = json.loads(value)
                    banned_groups_config['TRACKERS'][key_upper] = parsed_config
                except json.JSONDecodeError:
                    continue
            elif value.strip() and not value.startswith('#'):
                banned_groups_config['TRACKERS'][key_upper] = {'api_key': value.strip()}
    
    return banned_groups_config

def extract_unique_items_from_db(column, table='client_searchee', where_clause=None):
    """Extract unique items from database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        base_query = f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL AND {column} != '' AND {column} != 'null'"
        
        if where_clause:
            base_query += f" AND {where_clause}"
        
        cursor.execute(base_query)
        rows = cursor.fetchall()
        conn.close()
        
        return [row[0] for row in rows if row[0]]
        
    except Exception as e:
        print(f"Error extracting {column}: {e}")
        return []

def extract_unique_trackers_from_db():
    """Extract all unique tracker domains from database."""
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

def map_domain_to_abbreviation(domain):
    """Map a tracker domain to its abbreviation."""
    if not domain:
        return None
    
    domain_lower = domain.lower().strip()
    
    # Create matches sorted by length (longest first)
    matches = []
    for abbrev, variants in TRACKER_MAPPING.items():
        for variant in variants:
            matches.append((abbrev, variant.lower()))
    
    matches.sort(key=lambda x: len(x[1]), reverse=True)
    
    # Try exact matches first
    for abbrev, variant in matches:
        if domain_lower == variant:
            return abbrev
    
    # Try partial matches for tracker.domain.org cases
    for abbrev, variant in matches:
        if variant in domain_lower and len(variant) > 3:
            return abbrev
    
    return None

def build_tracker_mapping():
    """Build comprehensive tracker mapping."""
    unique_domains = extract_unique_trackers_from_db()
    print(f"Found {len(unique_domains)} unique tracker domains")
    
    domain_to_abbrev = {}
    mapped_trackers = set()
    
    for domain in unique_domains:
        abbrev = map_domain_to_abbreviation(domain)
        if abbrev:
            domain_to_abbrev[domain] = abbrev
            mapped_trackers.add(abbrev)
    
    print(f"Mapped {len(domain_to_abbrev)} domains to {len(mapped_trackers)} trackers")
    return domain_to_abbrev, sorted(mapped_trackers)

def is_single_episode(filename, config):
    """Check if filename is a single episode."""
    patterns = config['FILTERING'].get('single_episode_patterns', 
                                      r'S\d{2}E\d{2},EP?\d+,Episode\s*\d+,\d{4}[.\-]\d{2}[.\-]\d{2}').split(',')
    filename_lower = filename.lower()
    
    for pattern in patterns:
        pattern = pattern.strip()
        if pattern and re.search(pattern, filename_lower, re.IGNORECASE):
            return True
    
    return False

def is_season_from_files(files_json):
    """Check if torrent represents a season based on files."""
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
                if season_pattern.search(file_info['name']):
                    episode_count += 1
        
        return (episode_count > 1, episode_count)
            
    except (json.JSONDecodeError, TypeError):
        return False, 0

def is_video_content(name, files_json=None):
    """Check if content is video-related."""
    # Check if it's a season
    is_season, _ = is_season_from_files(files_json)
    if is_season:
        return True
    
    # Check file extension
    if Path(name).suffix.lower() in VIDEO_EXTENSIONS:
        return True
    
    # Check files in JSON
    if files_json:
        try:
            files = json.loads(files_json)
            if isinstance(files, list):
                for file_info in files:
                    if isinstance(file_info, dict) and 'name' in file_info:
                        if Path(file_info['name']).suffix.lower() in VIDEO_EXTENSIONS:
                            return True
        except (json.JSONDecodeError, TypeError):
            pass
    
    # Check video patterns
    name_lower = name.lower()
    for pattern in VIDEO_PATTERNS:
        if re.search(pattern, name_lower, re.IGNORECASE):
            return True
    
    return False

def create_torrent_item(row, domain_to_abbrev, enabled_trackers, config):
    """Create torrent item from database row."""
    name, info_hash, save_path, trackers_json, category_data, files_json = row
    
    # Check if video content
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
                'categories': str(category_data).split(',') if category_data else [],
                'is_season': is_season,
                'episode_count': episode_count,
                'files_json': files_json
            }
    
    except json.JSONDecodeError:
        pass
    
    return None

def normalize_content_name(filename):
    """Normalize content name for duplicate detection."""
    normalized = (Path(filename).stem + Path(filename).suffix).lower()
    normalized = re.sub(r'[.\-_]', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized

def process_content_groups(content_groups, enabled_trackers):
    """Process content groups and handle duplicates."""
    results = []
    
    for normalized_name, items in content_groups.items():
        if len(items) > 1:
            # Handle duplicates - merge tracker info
            merged_found_trackers = set()
            merged_categories = set()
            
            for item in items:
                merged_found_trackers.update(item['found_trackers'])
                merged_categories.update(item['categories'])
            
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
    
    return results

async def analyze_missing_trackers(no_banned_filter=False, verbose=False):
    """Main analysis function."""
    try:
        # Build tracker mapping
        domain_to_abbrev, available_trackers = build_tracker_mapping()
        
        if not available_trackers:
            print("No trackers found")
            return [], []
        
        # Load config
        config = load_config(available_trackers)
        enabled_trackers = get_enabled_trackers_from_config(config, available_trackers)
        
        # Check banned groups filtering
        banned_groups_enabled = (
            get_config_bool(config, 'BANNED_GROUPS', 'enabled', True) and 
            not no_banned_filter
        )
        
        print(f"Banned groups filtering: {'Enabled' if banned_groups_enabled else 'Disabled'}")
        
        # Query database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
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
            print("No torrents found")
            return [], []
        
        print(f"Analyzing {total_torrents} torrents...")
        
        # Process torrents
        content_groups = defaultdict(list)
        start_time = time.time()
        
        for i, row in enumerate(torrent_rows):
            print_progress_bar(i + 1, total_torrents, start_time, "Processing")
            
            item_data = create_torrent_item(row, domain_to_abbrev, enabled_trackers, config)
            if item_data:
                normalized_name = normalize_content_name(item_data['name'])
                content_groups[normalized_name].append(item_data)
        
        print()  # New line after progress bar
        
        results = process_content_groups(content_groups, enabled_trackers)
        
        results = process_content_groups(content_groups, enabled_trackers)
        
        # Apply personal filters first
        if results:
            print("Applying personal filters...")
            results, personal_filter_results = apply_personal_filters(results, config)
            display_personal_filter_results(personal_filter_results, verbose)
        
        # Apply banned groups filtering
        if banned_groups_enabled and results:
            print("Filtering banned release groups...")
            
            base_dir = os.path.dirname(os.path.abspath(__file__))
            banned_groups_config = fix_config_parsing(config)
            
            try:
                filtered_results, banned_torrents, filtering_stats = await filter_torrents_by_banned_groups(
                    results, enabled_trackers, banned_groups_config, base_dir, verbose
                )
                
                print(f"Filtered: {filtering_stats['passed_count']}/{filtering_stats['total_checked']} torrents")
                
                if filtering_stats['banned_count'] > 0 and verbose:
                    print(f"Banned groups breakdown:")
                    for tracker, count in filtering_stats['by_tracker'].items():
                        if count > 0:
                            print(f"  {tracker}: {count} torrents")
                
                results = filtered_results
                
            except Exception as e:
                print(f"Warning: Banned groups filtering failed: {e}")
        
        conn.close()
        return results, []
        
    except Exception as e:
        print(f"Error: {e}")
        return [], []

def generate_upload_commands(results, output_file=None, clean_output=False):
    """Generate upload commands file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    appdata_dir = Path(LOG_DIR)
    appdata_dir.mkdir(parents=True, exist_ok=True)

    if output_file:
        filename = appdata_dir / Path(output_file).name
    else:
        filename = appdata_dir / f"upload_commands_{timestamp}.txt"
    
    print("Generating upload commands...")
    
    with open(filename, 'w') as f:
        if not clean_output:
            f.write(f"# Generated {datetime.now()}\n")
            f.write(f"# Total torrents: {len(results)}\n\n")
        
        for item in sorted(results, key=lambda x: x['name'].lower()):
            if not clean_output:
                f.write(f"# {item['name']}\n")
                if item.get('is_season') and item.get('episode_count'):
                    f.write(f"# Season with {item['episode_count']} episodes\n")
                f.write(f"# Missing: {', '.join(item['missing_trackers']) if item['missing_trackers'] else 'None'}\n")
                f.write(f"# Found: {', '.join(item['found_trackers']) if item['found_trackers'] else 'None'}\n")
            
            # Create upload command
            full_path = Path(item["path"]) / item["name"]
            
            if item['missing_trackers']:
                tracker_list = ','.join(item['missing_trackers'])
                f.write(f'python3 upload.py "{full_path}" --trackers {tracker_list}\n')
            else:
                f.write(f'# No missing trackers for: {full_path}\n')
            
            if not clean_output:
                f.write('\n')
    
    print(f"Commands written to: {filename}")
    return filename

def extract_unique_categories_from_db():
    """Extract all unique categories from database."""
    category_data = extract_unique_items_from_db('category')
    unique_categories = set()
    
    for category in category_data:
        if not category:
            continue
            
        category_str = str(category).strip()
        
        # Split by common separators
        separators = [',', ';', '|', '/']
        categories = [category_str]
        
        for sep in separators:
            new_categories = []
            for cat in categories:
                new_categories.extend([c.strip() for c in cat.split(sep) if c.strip()])
            categories = new_categories
        
        # Clean categories
        for cat in categories:
            cleaned_cat = cat.strip().strip('\'"[]{}()')
            if cleaned_cat and cleaned_cat.lower() not in ['null', 'none', '']:
                unique_categories.add(cleaned_cat)
    
    return sorted(unique_categories)

def prompt_category_filter(available_categories, config):
    """Prompt user to select categories to filter by."""
    if not available_categories:
        return None
    
    # Check auto-filtering
    if get_config_bool(config, 'GENERAL', 'auto_filter_categories'):
        default_cats = config['GENERAL'].get('default_categories', 'Movies,TV').split(',')
        default_cats = [cat.strip() for cat in default_cats if cat.strip()]
        valid_defaults = [cat for cat in default_cats if cat in available_categories]
        if valid_defaults:
            print(f"Auto-filtering enabled. Using: {', '.join(valid_defaults)}")
            return valid_defaults
    
    print(f"\nFound categories: {', '.join(available_categories)}")
    print("\nFilter by specific categories? (Y/N)")
    print("Y = Select categories to show")
    print("N = Show all categories")
    
    while True:
        choice = input().strip().upper()
        if choice == 'Y':
            print(f"\nSelect categories (comma-separated):")
            print(f"Available: {', '.join(available_categories)}")
            
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
                    print("No valid categories. Try again.")
        elif choice == 'N':
            return None
        else:
            print("Please enter Y or N:")

def apply_personal_filters(results, config):
    """Apply personal filters based on format, resolution, audio, etc."""
    
    if not get_config_bool(config, 'PERSONAL_FILTERS', 'enabled', False):
        return results, {}
    
    case_sensitive = get_config_bool(config, 'PERSONAL_FILTERS', 'case_sensitive', False)
    filter_mode = config['PERSONAL_FILTERS'].get('filter_mode', 'exclude').lower()
    
    # Get filter criteria
    filters = {
        'format': {
            'include': [f.strip() for f in config['PERSONAL_FILTERS'].get('format_include', '').split(',') if f.strip()],
            'exclude': [f.strip() for f in config['PERSONAL_FILTERS'].get('format_exclude', '').split(',') if f.strip()]
        },
        'resolution': {
            'include': [r.strip() for r in config['PERSONAL_FILTERS'].get('resolution_include', '').split(',') if r.strip()],
            'exclude': [r.strip() for r in config['PERSONAL_FILTERS'].get('resolution_exclude', '').split(',') if r.strip()]
        },
        'audio': {
            'include': [a.strip() for a in config['PERSONAL_FILTERS'].get('audio_include', '').split(',') if a.strip()],
            'exclude': [a.strip() for a in config['PERSONAL_FILTERS'].get('audio_exclude', '').split(',') if a.strip()]
        },
        'channels': {
            'include': [c.strip() for c in config['PERSONAL_FILTERS'].get('channels_include', '').split(',') if c.strip()],
            'exclude': [c.strip() for c in config['PERSONAL_FILTERS'].get('channels_exclude', '').split(',') if c.strip()]
        },
        'special_flags': {
            'include': [s.strip() for s in config['PERSONAL_FILTERS'].get('special_flags_include', '').split(',') if s.strip()],
            'exclude': [s.strip() for s in config['PERSONAL_FILTERS'].get('special_flags_exclude', '').split(',') if s.strip()]
        }
    }
    
    def normalize_text(text):
        return text if case_sensitive else text.lower()
    
    def check_criteria_in_name(name, criteria_list):
        """Check if any criteria appears in the name."""
        name_normalized = normalize_text(name)
        for criteria in criteria_list:
            criteria_normalized = normalize_text(criteria)
            # Check different patterns
            patterns = [
                criteria_normalized,
                f".{criteria_normalized}.",
                f"-{criteria_normalized}.",
                f".{criteria_normalized}-",
                f"[{criteria_normalized}]",
                f"({criteria_normalized})",
            ]
            
            for pattern in patterns:
                if pattern in name_normalized:
                    return True
        return False
    
    def should_include_torrent(torrent_name):
        """Determine if torrent should be included."""
        for filter_type, filter_data in filters.items():
            include_list = filter_data['include']
            exclude_list = filter_data['exclude']
            
            # Include list - torrent MUST match at least one
            if include_list:
                if not check_criteria_in_name(torrent_name, include_list):
                    return False, f"Missing required {filter_type}: {', '.join(include_list)}"
            
            # Exclude list - torrent MUST NOT match any
            if exclude_list:
                if check_criteria_in_name(torrent_name, exclude_list):
                    for excluded in exclude_list:
                        if check_criteria_in_name(torrent_name, [excluded]):
                            return False, f"Contains excluded {filter_type}: {excluded}"
        
        return True, None
    
    # Apply filters
    filtered_results = []
    stats = {
        'total_checked': len(results),
        'passed_count': 0,
        'filtered_count': 0,
        'filter_reasons': {}
    }
    
    for result in results:
        torrent_name = result.get('name', '')
        should_include, reason = should_include_torrent(torrent_name)
        
        if should_include:
            filtered_results.append(result)
            stats['passed_count'] += 1
        else:
            stats['filtered_count'] += 1
            if reason not in stats['filter_reasons']:
                stats['filter_reasons'][reason] = 0
            stats['filter_reasons'][reason] += 1
    
    return filtered_results, {'stats': stats}

def display_personal_filter_results(filter_results, verbose=False):
    """Display personal filtering results."""
    if not filter_results or 'stats' not in filter_results:
        return
    
    stats = filter_results['stats']
    
    print(f"\nPersonal Filtering Results:")
    print(f"  Total torrents: {stats['total_checked']}")
    print(f"  Passed filters: {stats['passed_count']}")
    print(f"  Filtered out: {stats['filtered_count']}")
    
    if stats['filter_reasons'] and verbose:
        print(f"  Filter breakdown:")
        for reason, count in sorted(stats['filter_reasons'].items()):
            print(f"    {reason}: {count} torrents")

def filter_results_by_categories(results, selected_categories):
    """Filter results by selected categories."""
    if not selected_categories:
        return results
    
    matching_results = []
    
    for result in results:
        item_categories = result.get('categories', [])
        
        # Check if any item category matches selected categories
        for selected_cat in selected_categories:
            if any(selected_cat.lower().strip() == item_cat.lower().strip() 
                   for item_cat in item_categories):
                matching_results.append(result)
                break
    
    return matching_results

def display_results(results, verbose=False, selected_categories=None, total_results=0):
    """Display analysis results."""
    print(f"\n{Colors.BOLD}Missing Torrents by Tracker:{Colors.END}")
    print("=" * 60)
    
    # Show filtering info
    if selected_categories:
        print(f"{Colors.CYAN}Filtered by: {', '.join(selected_categories)}{Colors.END}")
        print(f"{Colors.WHITE}Showing {len(results)} of {total_results} total results{Colors.END}\n")
    
    for item in sorted(results, key=lambda x: x['name'].lower()):
        print(f"\n{Colors.GREEN}{Colors.BOLD}{item['name']}{Colors.END}")
        
        # Show type info
        if item.get('is_season') and item.get('episode_count'):
            print(f"   Type: Season ({item['episode_count']} episodes)")
        elif Path(item['name']).suffix:
            print(f"   Type: Single file")
        else:
            print(f"   Type: Folder")
        
        if verbose and item.get('duplicates'):
            print(f"   {Colors.BLUE}Duplicates: {', '.join(item['duplicates'])}{Colors.END}")
        
        print(f"   Path: {item['path']}")
        
        if item.get('categories'):
            print(f"   Categories: {', '.join(item['categories'])}")
        
        if item['missing_trackers']:
            print(f"   {Colors.RED}Missing: {', '.join(item['missing_trackers'])}{Colors.END}")
        
        if item['found_trackers']:
            print(f"   {Colors.YELLOW}Found: {', '.join(item['found_trackers'])}{Colors.END}")

def show_config_info(config):
    """Display current configuration."""
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
            print("Tracker filtering: None (all available)")
    
    if config.has_section('FILTERING'):
        include_episodes = get_config_bool(config, 'FILTERING', 'include_single_episodes')
        include_folders = get_config_bool(config, 'FILTERING', 'include_folders', True)
        prefer_seasons = get_config_bool(config, 'FILTERING', 'prefer_seasons_over_episodes', True)
        filter_banned = get_config_bool(config, 'FILTERING', 'filter_banned_groups', True)
        
        print(f"Single episodes: {'Include' if include_episodes else 'Exclude'}")
        print(f"Include folders: {'Yes' if include_folders else 'No'}")
        print(f"Prefer seasons: {'Yes' if prefer_seasons else 'No'}")
        print(f"Filter banned groups: {'Yes' if filter_banned else 'No'}")
    
    if config.has_section('BANNED_GROUPS'):
        enabled = get_config_bool(config, 'BANNED_GROUPS', 'enabled', True)
        verbose = get_config_bool(config, 'BANNED_GROUPS', 'verbose_filtering', False)
        
        print(f"Banned groups enabled: {'Yes' if enabled else 'No'}")
        print(f"Verbose filtering: {'Yes' if verbose else 'No'}")
    
    if config.has_section('PERSONAL_FILTERS'):
        enabled = get_config_bool(config, 'PERSONAL_FILTERS', 'enabled', False)
        case_sensitive = get_config_bool(config, 'PERSONAL_FILTERS', 'case_sensitive', False)
        filter_mode = config['PERSONAL_FILTERS'].get('filter_mode', 'exclude')
        
        print(f"\nPersonal Filters:")
        print(f"Enabled: {'Yes' if enabled else 'No'}")
        
        if enabled:
            print(f"Case sensitive: {'Yes' if case_sensitive else 'No'}")
            print(f"Default mode: {filter_mode}")
            
            # Show active filters
            filter_types = ['format', 'resolution', 'audio', 'channels', 'special_flags']
            for filter_type in filter_types:
                include_key = f'{filter_type}_include'
                exclude_key = f'{filter_type}_exclude'
                include_val = config['PERSONAL_FILTERS'].get(include_key, '').strip()
                exclude_val = config['PERSONAL_FILTERS'].get(exclude_key, '').strip()
                
                if include_val or exclude_val:
                    print(f"  {filter_type.replace('_', ' ').title()}:")
                    if include_val:
                        print(f"    Include: {include_val}")
                    if exclude_val:
                        print(f"    Exclude: {exclude_val}")
    
    print(f"\nConfig file: {CONFIG_FILE}")

def debug_tracker_mapping():
    """Debug tracker mapping."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    appdata_dir = Path(LOG_DIR)
    appdata_dir.mkdir(parents=True, exist_ok=True)
    debug_file = appdata_dir / f"tracker_debug_{timestamp}.txt"
    
    print("Running tracker mapping debug...")
    
    try:
        unique_domains = extract_unique_trackers_from_db()
        domain_to_abbrev, mapped_trackers = build_tracker_mapping()
        
        with open(debug_file, 'w') as f:
            f.write("TRACKER MAPPING DEBUG\n")
            f.write("=" * 40 + "\n\n")
            
            f.write(f"Total domains in DB: {len(unique_domains)}\n")
            f.write(f"Mapped domains: {len(domain_to_abbrev)}\n")
            f.write(f"Unique trackers: {len(mapped_trackers)}\n\n")
            
            f.write("DOMAIN MAPPINGS:\n")
            f.write("-" * 30 + "\n")
            for domain in sorted(unique_domains):
                abbrev = domain_to_abbrev.get(domain, "UNMAPPED")
                f.write(f"{domain:<30} -> {abbrev}\n")
            
            f.write(f"\nMAPPED TRACKERS:\n")
            f.write("-" * 30 + "\n")
            for abbrev in sorted(mapped_trackers):
                f.write(f"  {abbrev}\n")
            
            unmapped = [d for d in unique_domains if d not in domain_to_abbrev]
            if unmapped:
                f.write(f"\nUNMAPPED DOMAINS:\n")
                f.write("-" * 30 + "\n")
                for domain in sorted(unmapped):
                    f.write(f"  {domain}\n")
        
        print(f"Debug written to: {debug_file}")
        
    except Exception as e:
        print(f"Debug error: {e}")

def main():
    parser = argparse.ArgumentParser(description="Cross-Pollinator: Analyze missing torrents")
    
    parser.add_argument('-r', '--run', action='store_true', help='Run analysis')
    parser.add_argument('-o', '--output', nargs='?', const='default', help='Generate upload commands')
    parser.add_argument('-c', '--clean', action='store_true', help='Clean output (no colors/comments)')
    parser.add_argument('-t', '--trackers', action='store_true', help='Debug tracker mapping')
    parser.add_argument('--rm-filters', action='store_true', help='Skip category filtering')
    parser.add_argument('--config', action='store_true', help='Show configuration')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--no-ban', action='store_true', help='Skip banned groups filtering')
    parser.add_argument('--sync', action='store_true', help='Force synchronous mode')
    parser.add_argument('--debug-groups', action='store_true', help='Debug release group extraction and banned groups filtering')
    
    args = parser.parse_args()
    
    # Disable colors for clean output
    if args.clean:
        Colors.disable()
    
    if args.config:
        config = load_config()
        show_config_info(config)
        if not args.run and not args.trackers:
            return
    
    if not args.run and not args.trackers:
        parser.print_help()
        sys.exit(1)
    
    if not Path(DB_PATH).exists():
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)
    
    # Debug tracker mapping
    if args.trackers:
        debug_tracker_mapping()
        if not args.run:
            return
        print()
    
    print("Analyzing cross-seed database...")
    
    if banned_groups_enabled and results:
            print("Filtering banned release groups...")
            
            # Debug release group extraction (only if --debug-groups is enabled)
            if args.debug_groups:
                print("\nDEBUG: Release group extraction for sample torrents:")
                print("-" * 50)
                sample_count = 0
                for result in results:
                    if sample_count >= 10:  # Limit to first 10 for debugging
                        break
                    extracted_group = extract_release_group(result['name'])
                    print(f"'{result['name']}' -> Group: '{extracted_group}'")
                    sample_count += 1
                print("-" * 50)
            
            base_dir = os.path.dirname(os.path.abspath(__file__))
            banned_groups_config = fix_config_parsing(config)
            
            try:
                filtered_results, banned_torrents, filtering_stats = await filter_torrents_by_banned_groups(
                    results, enabled_trackers, banned_groups_config, base_dir, args.debug_groups
                )
                
                print(f"Filtered: {filtering_stats['passed_count']}/{filtering_stats['total_checked']} torrents")
                
                if filtering_stats['banned_count'] > 0 and (verbose or args.debug_groups):
                    print(f"Banned groups breakdown:")
                    for tracker, count in filtering_stats['by_tracker'].items():
                        if count > 0:
                            print(f"  {tracker}: {count} torrents")
                
                # Show detailed debug info if requested
                if args.debug_groups and banned_torrents:
                    print(f"\nDEBUG: Banned torrents details:")
                    print("-" * 50)
                    for torrent in banned_torrents[:5]:  # Show first 5 banned torrents
                        print(f"BANNED: {torrent['name']}")
                        if 'banned_info' in torrent:
                            for info in torrent['banned_info']:
                                print(f"  └─ {info['reason']}")
                    if len(banned_torrents) > 5:
                        print(f"... and {len(banned_torrents) - 5} more")
                    print("-" * 50)
                
                results = filtered_results
                
            except Exception as e:
                print(f"Warning: Banned groups filtering failed: {e}")
                if args.debug_groups:
                    import traceback
                    print("Full error traceback:")
                    traceback.print_exc()
    # Run analysis
    if args.sync:
        print("Note: Synchronous mode - banned groups filtering disabled")
        # For sync mode, we'll create a simple version without async
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            domain_to_abbrev, available_trackers = build_tracker_mapping()
            if not available_trackers:
                print("No trackers found")
                return
            
            config = load_config(available_trackers)
            enabled_trackers = get_enabled_trackers_from_config(config, available_trackers)
            
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
            content_groups = defaultdict(list)
            
            for row in torrent_rows:
                item_data = create_torrent_item(row, domain_to_abbrev, enabled_trackers, config)
                if item_data:
                    normalized_name = normalize_content_name(item_data['name'])
                    content_groups[normalized_name].append(item_data)
            
            results = process_content_groups(content_groups, enabled_trackers)
            conn.close()
            
        except Exception as e:
            print(f"Error: {e}")
            return
    else:
        try:
            results, _ = asyncio.run(analyze_missing_trackers(args.no_ban, args.verbose))
        except Exception as e:
            print(f"Async failed ({e}), trying sync mode")
            # Fallback to sync logic here if needed
            results = []
    
    if not results:
        print("No torrents need uploading to additional trackers")
        return
    
    print(f"Found {len(results)} torrents needing upload")
    
    # Handle category filtering (unless --rm-filters is used)
    selected_categories = None
    total_results = len(results)
    
    if not args.rm_filters:
        try:
            all_categories = extract_unique_categories_from_db()
            if all_categories:
                config = load_config()
                selected_categories = prompt_category_filter(all_categories, config)
                if selected_categories:
                    results = filter_results_by_categories(results, selected_categories)
                    if not results:
                        print("No results match selected categories")
                        return
        except Exception as e:
            print(f"Category filtering failed: {e}")
          
    if banned_groups_enabled and results:
            print("Filtering banned release groups...")
            
            # Debug release group extraction (only if --debug-groups is enabled)
            if args.debug_groups:
                print("\nDEBUG: Release group extraction for sample torrents:")
                print("-" * 50)
                sample_count = 0
                for result in results:
                    if sample_count >= 10:  # Limit to first 10 for debugging
                        break
                    extracted_group = extract_release_group(result['name'])
                    print(f"'{result['name']}' -> Group: '{extracted_group}'")
                    sample_count += 1
                print("-" * 50)
            
            base_dir = os.path.dirname(os.path.abspath(__file__))
            banned_groups_config = fix_config_parsing(config)
            
            try:
                filtered_results, banned_torrents, filtering_stats = await filter_torrents_by_banned_groups(
                    results, enabled_trackers, banned_groups_config, base_dir, args.debug_groups
                )
                
                print(f"Filtered: {filtering_stats['passed_count']}/{filtering_stats['total_checked']} torrents")
                
                if filtering_stats['banned_count'] > 0 and (verbose or args.debug_groups):
                    print(f"Banned groups breakdown:")
                    for tracker, count in filtering_stats['by_tracker'].items():
                        if count > 0:
                            print(f"  {tracker}: {count} torrents")
                
                # Show detailed debug info if requested
                if args.debug_groups and banned_torrents:
                    print(f"\nDEBUG: Banned torrents details:")
                    print("-" * 50)
                    for torrent in banned_torrents[:5]:  # Show first 5 banned torrents
                        print(f"BANNED: {torrent['name']}")
                        if 'banned_info' in torrent:
                            for info in torrent['banned_info']:
                                print(f"  └─ {info['reason']}")
                    if len(banned_torrents) > 5:
                        print(f"... and {len(banned_torrents) - 5} more")
                    print("-" * 50)
                
                results = filtered_results
                
            except Exception as e:
                print(f"Warning: Banned groups filtering failed: {e}")
                if args.debug_groups:
                    import traceback
                    print("Full error traceback:")
                    traceback.print_exc()
                  
    # Display results unless clean output
    if not args.clean:
        display_results(results, args.verbose, selected_categories, total_results)
    
    # Generate commands if requested
    if args.output is not None:
        output_file = args.output if args.output != 'default' else None
        commands_file = generate_upload_commands(results, output_file, args.clean)
        if not args.clean:
            print(f"\nUpload commands: {commands_file}")
    elif not args.clean:
        print("\nUse -o to generate upload commands")
    
    if not args.clean:
        print("\nAnalysis complete!")

if __name__ == "__main__":
    main()
