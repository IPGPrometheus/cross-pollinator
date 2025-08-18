#!/usr/bin/env python3
"""
Cross-Pollinator Uploader - Generate Upload Commands with Tracker Validation

Parses cross-seed database, validates tracker requirements using COMMON class, and generates upload.py commands.
"""
import os
import sqlite3
import sys
import argparse
import json
from collections import defaultdict
from pathlib import Path
from datetime import datetime

# Import the COMMON class for validation
try:
    from src.common import COMMON
    HAS_COMMON = True
except ImportError:
    print("⚠️  COMMON class not found, running without validation")
    HAS_COMMON = False

# Configuration
CROSS_SEED_DIR = "/cross-seed"
DB_PATH = "/cross-seed/cross-seed.db"
CONFIG_PATH = "/config/config.json"  # Path to upload assistant config

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
    'STC': ['STC', 'skipthecommerials'],
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

class TrackerValidator:
    """Validates torrents against tracker-specific requirements using COMMON class."""
    
    def __init__(self, config_path=None):
        self.config = self.load_config(config_path)
        self.common = COMMON(self.config) if HAS_COMMON else None
        self.validation_stats = defaultdict(lambda: {'total': 0, 'passed': 0, 'failed': 0, 'reasons': defaultdict(int)})
    
    def load_config(self, config_path):
        """Load upload assistant configuration."""
        if not config_path or not Path(config_path).exists():
            print(f"⚠️  Config not found at {config_path}, using basic validation")
            return {'TRACKERS': {}, 'DEFAULT': {}}
        
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Error loading config: {e}, using basic validation")
            return {'TRACKERS': {}, 'DEFAULT': {}}
    
    def get_basic_meta(self, file_path, torrent_name):
        """Create a basic meta object for validation."""
        if not self.common:
            return None
            
        try:
            # Create minimal meta object similar to upload assistant
            meta = {
                'path': str(file_path),
                'name': torrent_name,
                'base_dir': '/tmp',
                'uuid': 'validation',
                'debug': False
            }
            
            # Let COMMON's MediaInfoParser handle the file analysis
            if hasattr(self.common, 'parser'):
                # Use the existing parser from COMMON
                from pymediainfo import MediaInfo
                mi_dump = MediaInfo.parse(str(file_path), output="STRING", full=False)
                parsed_info = self.common.parser.parse_mediainfo(mi_dump)
                
                # Extract relevant info for validation
                meta.update({
                    'mediainfo': mi_dump,
                    'resolution': parsed_info.get('resolution', ''),
                    'video_codec': parsed_info.get('video_codec', ''),
                    'audio_codec': parsed_info.get('audio_codec', ''),
                    'duration': parsed_info.get('duration', 0),
                    'file_size': Path(file_path).stat().st_size if Path(file_path).exists() else 0
                })
            
            return meta
            
        except Exception as e:
            print(f"⚠️  Error creating meta for {file_path}: {e}")
            return None
    
    def validate_tracker_requirements(self, tracker, file_path, torrent_name):
        """Validate if torrent meets tracker-specific requirements using COMMON."""
        self.validation_stats[tracker]['total'] += 1
        
        # If no COMMON class available, skip validation
        if not self.common:
            reason = "COMMON class not available"
            self.validation_stats[tracker]['passed'] += 1
            return True, reason
        
        # Check if file exists
        if not Path(file_path).exists():
            reason = f"File not found: {file_path}"
            self.validation_stats[tracker]['failed'] += 1
            self.validation_stats[tracker]['reasons'][reason] += 1
            return False, reason
        
        # Get tracker config
        tracker_config = self.config.get('TRACKERS', {}).get(tracker, {})
        
        # If no specific config, assume it's valid
        if not tracker_config:
            self.validation_stats[tracker]['passed'] += 1
            return True, "No specific requirements configured"
        
        # Create meta object for validation
        meta = self.get_basic_meta(file_path, torrent_name)
        if not meta:
            reason = "Could not analyze media file"
            self.validation_stats[tracker]['failed'] += 1
            self.validation_stats[tracker]['reasons'][reason] += 1
            return False, reason
        
        # Perform validation checks using tracker config
        validation_result = self.perform_validation_checks(tracker, meta, tracker_config)
        
        if validation_result['valid']:
            self.validation_stats[tracker]['passed'] += 1
        else:
            self.validation_stats[tracker]['failed'] += 1
            self.validation_stats[tracker]['reasons'][validation_result['reason']] += 1
        
        return validation_result['valid'], validation_result['reason']
    
    def perform_validation_checks(self, tracker, meta, tracker_config):
        """Perform specific validation checks using tracker configuration."""
        # File size validation
        min_size_mb = tracker_config.get('min_file_size_mb', 0)
        max_size_gb = tracker_config.get('max_file_size_gb', float('inf'))
        
        file_size_mb = meta['file_size'] / (1024 * 1024)
        file_size_gb = meta['file_size'] / (1024 * 1024 * 1024)
        
        if min_size_mb > 0 and file_size_mb < min_size_mb:
            return {
                'valid': False, 
                'reason': f"File too small ({file_size_mb:.1f}MB < {min_size_mb}MB)"
            }
        
        if max_size_gb < float('inf') and file_size_gb > max_size_gb:
            return {
                'valid': False, 
                'reason': f"File too large ({file_size_gb:.1f}GB > {max_size_gb}GB)"
            }
        
        # Resolution validation
        allowed_resolutions = tracker_config.get('allowed_resolutions', [])
        if allowed_resolutions and meta.get('resolution'):
            resolution_match = any(res in meta['resolution'] for res in allowed_resolutions)
            if not resolution_match:
                return {
                    'valid': False,
                    'reason': f"Resolution not allowed ({meta['resolution']} not in {allowed_resolutions})"
                }
        
        # Codec validation
        allowed_codecs = tracker_config.get('allowed_codecs', [])
        if allowed_codecs and meta.get('video_codec'):
            codec_match = any(codec.upper() in meta['video_codec'].upper() for codec in allowed_codecs)
            if not codec_match:
                return {
                    'valid': False,
                    'reason': f"Codec not allowed ({meta['video_codec']} not in {allowed_codecs})"
                }
        
        # Duration validation
        min_duration_minutes = tracker_config.get('min_duration_minutes', 0)
        if min_duration_minutes > 0 and meta.get('duration', 0):
            duration_minutes = meta['duration'] / (60 * 1000)  # Convert to minutes
            if duration_minutes < min_duration_minutes:
                return {
                    'valid': False,
                    'reason': f"Duration too short ({duration_minutes:.1f}min < {min_duration_minutes}min)"
                }
        
        # Filename pattern validation
        import re
        
        forbidden_patterns = tracker_config.get('forbidden_filename_patterns', [])
        for pattern in forbidden_patterns:
            if re.search(pattern, meta['name'], re.IGNORECASE):
                return {
                    'valid': False,
                    'reason': f"Filename matches forbidden pattern: {pattern}"
                }
        
        required_patterns = tracker_config.get('required_filename_patterns', [])
        for pattern in required_patterns:
            if not re.search(pattern, meta['name'], re.IGNORECASE):
                return {
                    'valid': False,
                    'reason': f"Filename missing required pattern: {pattern}"
                }
        
        # Tracker-specific custom validation
        custom_result = self.custom_tracker_validation(tracker, meta, tracker_config)
        if not custom_result['valid']:
            return custom_result
        
        return {'valid': True, 'reason': 'All requirements met'}
    
    def custom_tracker_validation(self, tracker, meta, tracker_config):
        """Perform tracker-specific custom validation logic."""
        
        # BLU (Blutopia) specific rules
        if tracker == 'BLU':
            # Example: Blutopia might require specific naming conventions
            if 'bluray' not in meta['name'].lower() and 'web-dl' not in meta['name'].lower():
                return {
                    'valid': False,
                    'reason': 'BLU requires BluRay or WEB-DL in filename'
                }
        
        # AITHER specific rules
        elif tracker == 'AITHER':
            # Example: AITHER might have specific codec preferences
            if meta.get('video_codec', '').upper() in ['XVID', 'DIVX']:
                return {
                    'valid': False,
                    'reason': 'AITHER does not accept old codecs like XviD/DivX'
                }
        
        # HDB (HDBits) specific rules
        elif tracker == 'HDB':
            # Example: HDB might require remux for certain content
            file_size_gb = meta['file_size'] / (1024 * 1024 * 1024)
            if file_size_gb > 20 and 'remux' not in meta['name'].lower():
                return {
                    'valid': False,
                    'reason': 'HDB prefers remux for large files'
                }
        
        # PTP specific rules
        elif tracker == 'PTP':
            # Example: PTP might have strict quality requirements
            if any(word in meta['name'].lower() for word in ['cam', 'ts', 'tc', 'r5']):
                return {
                    'valid': False,
                    'reason': 'PTP does not accept low quality sources'
                }
        
        # Add more tracker-specific rules as needed...
        
        return {'valid': True, 'reason': 'Custom validation passed'}
    
    def print_validation_stats(self):
        """Print validation statistics."""
        if not self.validation_stats:
            return
        
        print("\n📊 Tracker Validation Statistics:")
        print("=" * 80)
        
        for tracker in sorted(self.validation_stats.keys()):
            stats = self.validation_stats[tracker]
            pass_rate = (stats['passed'] / stats['total'] * 100) if stats['total'] > 0 else 0
            
            print(f"\n🎯 {tracker}:")
            print(f"   Total: {stats['total']}, Passed: {stats['passed']}, Failed: {stats['failed']} ({pass_rate:.1f}% pass rate)")
            
            if stats['reasons']:
                print("   Top failure reasons:")
                for reason, count in sorted(stats['reasons'].items(), key=lambda x: x[1], reverse=True)[:3]:
                    print(f"     • {reason}: {count}")

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

def validate_and_filter_results(results, validator):
    """Validate torrents against tracker requirements and filter results."""
    print("\n🔍 Validating torrents against tracker requirements...")
    
    validated_results = []
    
    for item in results:
        torrent_name = item['name']
        base_path = Path(item['path'])
        full_file_path = base_path / torrent_name
        
        # Validate each missing tracker
        valid_trackers = []
        invalid_trackers = []
        
        for tracker in item['missing_trackers']:
            is_valid, reason = validator.validate_tracker_requirements(tracker, full_file_path, torrent_name)
            if is_valid:
                valid_trackers.append(tracker)
            else:
                invalid_trackers.append((tracker, reason))
        
        # Only include torrents that have at least one valid tracker
        if valid_trackers:
            validated_item = item.copy()
            validated_item['missing_trackers'] = valid_trackers
            validated_item['invalid_trackers'] = invalid_trackers
            validated_results.append(validated_item)
    
    return validated_results

def generate_upload_commands(results, output_file=None):
    """Generate upload.py commands and save them to persistent appdata."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Ensure LOG_DIR is a Path object for consistency
    appdata_dir = Path(LOG_DIR)
    appdata_dir.mkdir(parents=True, exist_ok=True)
    
    if output_file:
        filename = appdata_dir / Path(output_file).name
    else:
        filename = appdata_dir / f"upload_commands_{timestamp}.txt"
    
    with open(filename, 'w') as f:
        f.write(f"# UAhelper: Generated {datetime.now()}\n")
        f.write(f"# Total files needing upload: {len(results)}\n")
        f.write(f"# Files validated using COMMON class{'✓' if HAS_COMMON else '✗'}\n\n")
        
        for item in sorted(results, key=lambda x: x['name'].lower()):
            f.write(f"# {item['name']}\n")
            f.write(f"# Valid for upload to: {', '.join(item['missing_trackers'])}\n")
            f.write(f"# Found on: {', '.join(item['found_trackers']) if item['found_trackers'] else 'None'}\n")
            
            if item.get('invalid_trackers'):
                f.write(f"# Invalid for: {', '.join([f'{t}({r})' for t, r in item['invalid_trackers']])}\n")
            
            # Construct the full file path
            base_path = Path(item["path"])
            torrent_name = item["name"]
            full_file_path = base_path / torrent_name
            
            f.write(f'python3 upload.py "{full_file_path}"\n\n')

    print(f"✅ Upload commands written to: {filename}")
    return filename

def main():
    parser = argparse.ArgumentParser(
        description="Cross-Pollinator: Analyze and validate missing torrents using COMMON class"
    )
    parser.add_argument('--run', action='store_true', help='Run analysis and show missing torrents')
    parser.add_argument('--output', nargs='?', const='default', help='Generate upload commands file (optional filename)')
    parser.add_argument('--config', default=CONFIG_PATH, help='Path to upload assistant config file')
    parser.add_argument('--skip-validation', action='store_true', help='Skip tracker requirement validation')
    parser.add_argument('--stats', action='store_true', help='Show validation statistics')
    
    args = parser.parse_args()
    
    if not args.run:
        parser.print_help()
        sys.exit(1)
    
    if not Path(DB_PATH).exists():
        print(f"❌ Database not found: {DB_PATH}")
        sys.exit(1)
    
    print("🔎 Analyzing cross-seed database for missing torrents...")
    if HAS_COMMON:
        print("✅ COMMON class loaded successfully")
    else:
        print("⚠️  COMMON class not available - validation disabled")
    
    results = get_torrents_with_paths()
    
    if not results:
        print("✅ No torrents with paths found needing upload")
        return
    
    print(f"📊 Found {len(results)} torrents with file paths needing upload")
    
    # Initialize validator and filter results
    if not args.skip_validation and HAS_COMMON:
        validator = TrackerValidator(args.config)
        results = validate_and_filter_results(results, validator)
        
        if not results:
            print("❌ No torrents passed validation requirements")
            if args.stats:
                validator.print_validation_stats()
            return
        
        print(f"✅ {len(results)} torrents passed validation")
    elif args.skip_validation:
        print("⚠️  Skipping validation as requested")
    else:
        print("⚠️  Skipping validation - COMMON class not available")
    
    # Display missing torrents and their trackers
    print("\n🎬 Missing Torrents by Tracker:")
    print("=" * 80)
    
    for item in sorted(results, key=lambda x: x['name'].lower()):
        print(f"\n🎞️  {item['name']}")
        print(f"   📁 Path: {item['path']}")
        print(f"   ❌ Missing from: {', '.join(item['missing_trackers'])}")
        if item['found_trackers']:
            print(f"   ✅ Found on: {', '.join(item['found_trackers'])}")
        else:
            print(f"   ✅ Found on: None")
        
        if not args.skip_validation and HAS_COMMON and item.get('invalid_trackers'):
            invalid_list = [f"{t} ({r})" for t, r in item['invalid_trackers']]
            print(f"   ⚠️  Invalid for: {', '.join(invalid_list)}")
    
    # Show validation statistics
    if not args.skip_validation and HAS_COMMON and args.stats:
        validator.print_validation_stats()
    
    # Generate upload commands only if --output is specified
    if args.output is not None:
        output_file = args.output if args.output != 'default' else None
        commands_file = generate_upload_commands(results, output_file)
        print(f"\n📝 Upload commands written to: {commands_file}")
        print(f"💡 Review {commands_file} before executing upload commands")
    else:
        print(f"\n💡 Use --output to generate upload commands file")
    
    print("\n✨ Analysis complete!")

if __name__ == "__main__":
    main()