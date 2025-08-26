#!/usr/bin/env python3
"""
Banned Groups Module for Cross-Pollinator
Filters out torrents with banned release groups to reduce unnecessary cross-pollination attempts.
"""
import os
import re
import json
import asyncio
import httpx
from datetime import datetime, timedelta
from pathlib import Path
from rich.console import Console

console = Console()

class BannedGroupsChecker:
    """Handles checking and filtering of banned release groups."""
    
    def __init__(self, config, base_dir):
        self.config = config
        self.base_dir = base_dir
        self.banned_groups_cache = {}
        
    def extract_release_group_from_name(self, torrent_name):
        """
        Extract release group from torrent name using common patterns.
        Looks for groups in brackets, after dashes, or at the end of filename.
        """
        if not torrent_name:
            return None
            
        # Remove file extension
        name = Path(torrent_name).stem
        
        # Common release group patterns (in order of preference)
        patterns = [
            # Groups in square brackets at the end: [GroupName]
            r'\[([^\]]+)\]$',
            # Groups in square brackets anywhere: [GroupName]
            r'\[([^\]]+)\]',
            # Groups after dash at end: -GroupName
            r'-([A-Za-z0-9]+)$',
            # Groups in parentheses at end: (GroupName)
            r'\(([^)]+)\)$',
            # Groups after last dot (before extension): .GroupName
            r'\.([A-Za-z0-9]+)$',
            # Groups with common prefixes
            r'(?:^|[\.\-\s])([A-Za-z0-9]{2,15})(?:[\.\-\s]|$)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, name, re.IGNORECASE)
            if matches:
                # Return the first/best match, cleaned up
                group = matches[0].strip()
                # Filter out obvious non-groups (years, resolutions, etc.)
                if not self._is_likely_release_group(group):
                    continue
                return group
                
        return None
    
    def _is_likely_release_group(self, candidate):
        """
        Check if a candidate string is likely a release group name.
        Filters out common false positives.
        """
        if not candidate or len(candidate) < 2:
            return False
            
        candidate_lower = candidate.lower()
        
        # Common false positives to exclude
        false_positives = {
            # Years
            r'^\d{4}$',
            # Resolutions
            r'^(720p|1080p|2160p|4k)$',
            # Video codecs
            r'^(x264|x265|h264|h265|xvid|divx)$',
            # Audio codecs
            r'^(aac|ac3|dts|flac|mp3)$',
            # Sources
            r'^(bluray|bdrip|dvdrip|webrip|webdl|hdtv|pdtv)$',
            # Common words
            r'^(the|and|of|in|to|for|with|by)$',
            # Episode/season indicators
            r'^(s\d+|e\d+|ep\d+|season|episode)$',
            # Quality indicators
            r'^(hd|sd|uhd|hdr|sdr)$',
        }
        
        for pattern in false_positives:
            if re.match(pattern, candidate_lower):
                return False
        
        # Additional heuristics for valid groups
        # Groups are usually alphanumeric, may contain some special chars
        if not re.match(r'^[A-Za-z0-9\-_.]+$', candidate):
            return False
            
        # Very short candidates are often false positives
        if len(candidate) < 3 and not candidate.isupper():
            return False
            
        return True
    
    async def load_banned_groups_for_tracker(self, tracker):
        """Load banned groups for a specific tracker."""
        tracker_upper = tracker.upper()
        
        # Check cache first
        if tracker_upper in self.banned_groups_cache:
            cache_data = self.banned_groups_cache[tracker_upper]
            # Check if cache is still valid (less than 24 hours old)
            if datetime.now() - cache_data['timestamp'] < timedelta(hours=24):
                return cache_data['groups']
        
        # Try to load from existing file or fetch new data
        file_path = os.path.join(self.base_dir, 'data', 'banned', f'{tracker_upper}_banned_groups.json')
        
        banned_groups = []
        
        # Check if we have a local file and if it's recent
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Check if file is recent (within 24 hours)
                last_updated = datetime.strptime(data.get('last_updated', '1970-01-01'), '%Y-%m-%d')
                if datetime.now() - last_updated < timedelta(days=1):
                    banned_groups_str = data.get('banned_groups', '')
                    if banned_groups_str:
                        banned_groups = [group.strip() for group in banned_groups_str.split(',')]
                    
                    # Cache the result
                    self.banned_groups_cache[tracker_upper] = {
                        'groups': banned_groups,
                        'timestamp': datetime.now()
                    }
                    
                    return banned_groups
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                console.print(f"[yellow]Warning: Could not load banned groups from {file_path}: {e}[/yellow]")
        
        # Try to fetch new data if we don't have recent local data
        try:
            new_banned_groups = await self._fetch_banned_groups_from_api(tracker_upper)
            if new_banned_groups:
                banned_groups = new_banned_groups
                # Cache the result
                self.banned_groups_cache[tracker_upper] = {
                    'groups': banned_groups,
                    'timestamp': datetime.now()
                }
        except Exception as e:
            console.print(f"[yellow]Warning: Could not fetch banned groups for {tracker_upper}: {e}[/yellow]")
        
        return banned_groups
    
    async def _fetch_banned_groups_from_api(self, tracker):
        """Fetch banned groups from tracker API (similar to original implementation)."""
        url = None
        if tracker == "AITHER":
            url = f'https://{tracker.lower()}.cc/api/blacklists/releasegroups'
        elif tracker == "LST":
            url = f"https://{tracker.lower()}.gg/api/bannedReleaseGroups"
        
        if not url or tracker not in self.config.get('TRACKERS', {}):
            return []
        
        api_key = self.config['TRACKERS'][tracker].get('api_key', '').strip()
        if not api_key:
            return []
        
        headers = {
            'Authorization': f"Bearer {api_key}",
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        all_data = []
        next_cursor = None
        
        try:
            async with httpx.AsyncClient() as client:
                while True:
                    params = {'cursor': next_cursor, 'per_page': 100} if next_cursor else {'per_page': 100}
                    response = await client.get(url, headers=headers, params=params, timeout=30.0)
                    
                    if response.status_code == 200:
                        response_json = response.json()
                        
                        if isinstance(response_json, list):
                            all_data.extend(response_json)
                            break
                        elif isinstance(response_json, dict):
                            page_data = response_json.get('data', [])
                            if isinstance(page_data, list):
                                all_data.extend(page_data)
                            
                            meta_info = response_json.get('meta', {})
                            next_cursor = meta_info.get('next_cursor')
                            if not next_cursor:
                                break
                        else:
                            break
                    elif response.status_code == 404:
                        console.print(f"[yellow]Warning: Tracker {tracker} returned 404 for banned groups API[/yellow]")
                        break
                    else:
                        console.print(f"[yellow]Warning: Received status code {response.status_code} for tracker {tracker}[/yellow]")
                        break
        
        except Exception as e:
            console.print(f"[red]Error fetching banned groups for {tracker}: {e}[/red]")
            return []
        
        # Extract group names
        banned_groups = []
        for item in all_data:
            if isinstance(item, dict) and 'name' in item:
                banned_groups.append(item['name'])
        
        # Save to file for future use
        if banned_groups:
            await self._save_banned_groups_to_file(tracker, banned_groups)
        
        return banned_groups
    
    async def _save_banned_groups_to_file(self, tracker, banned_groups):
        """Save banned groups to local file."""
        file_path = os.path.join(self.base_dir, 'data', 'banned', f'{tracker}_banned_groups.json')
        
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            file_content = {
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
                "banned_groups": ', '.join(banned_groups),
                "raw_data": [{"name": group} for group in banned_groups]
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(file_content, f, indent=4)
                
        except Exception as e:
            console.print(f"[red]Error saving banned groups to {file_path}: {e}[/red]")
    
    async def is_banned_for_tracker(self, torrent_name, tracker):
        """
        Check if a torrent name contains a banned release group for a specific tracker.
        Returns (is_banned, group_name, reason)
        """
        if not torrent_name or not tracker:
            return False, None, None
        
        # Extract release group from torrent name
        release_group = self.extract_release_group_from_name(torrent_name)
        if not release_group:
            return False, None, "No release group found"
        
        # Get banned groups for this tracker
        banned_groups = await self.load_banned_groups_for_tracker(tracker)
        if not banned_groups:
            return False, release_group, "No banned groups data available"
        
        # Check if the release group is banned (case-insensitive)
        release_group_lower = release_group.lower()
        for banned_group in banned_groups:
            if isinstance(banned_group, str) and banned_group.lower() == release_group_lower:
                return True, release_group, f"Group '{release_group}' is banned on {tracker}"
        
        return False, release_group, None
    
    async def filter_banned_torrents(self, torrents, trackers_to_check, verbose=False):
        """
        Filter out torrents that have banned release groups for any of the specified trackers.
        
        Args:
            torrents: List of torrent items with 'name' field
            trackers_to_check: List of tracker names to check against
            verbose: Whether to print detailed filtering information
            
        Returns:
            (filtered_torrents, banned_torrents, filtering_stats)
        """
        if not torrents or not trackers_to_check:
            return torrents, [], {}
        
        filtered_torrents = []
        banned_torrents = []
        filtering_stats = {
            'total_checked': len(torrents),
            'banned_count': 0,
            'passed_count': 0,
            'by_tracker': {tracker: 0 for tracker in trackers_to_check},
            'by_group': {}
        }
        
        if verbose:
            console.print(f"[cyan]Checking {len(torrents)} torrents against banned groups for trackers: {', '.join(trackers_to_check)}[/cyan]")
        
        for i, torrent in enumerate(torrents):
            torrent_name = torrent.get('name', '')
            is_banned_anywhere = False
            banned_info = []
            
            # Check against each tracker
            for tracker in trackers_to_check:
                is_banned, group_name, reason = await self.is_banned_for_tracker(torrent_name, tracker)
                
                if is_banned:
                    is_banned_anywhere = True
                    banned_info.append({
                        'tracker': tracker,
                        'group': group_name,
                        'reason': reason
                    })
                    filtering_stats['by_tracker'][tracker] += 1
                    
                    if group_name not in filtering_stats['by_group']:
                        filtering_stats['by_group'][group_name] = 0
                    filtering_stats['by_group'][group_name] += 1
            
            if is_banned_anywhere:
                filtering_stats['banned_count'] += 1
                torrent['banned_info'] = banned_info
                banned_torrents.append(torrent)
                
                if verbose:
                    console.print(f"[red]BANNED: {torrent_name}[/red]")
                    for info in banned_info:
                        console.print(f"  [yellow]└─ {info['reason']}[/yellow]")
            else:
                filtering_stats['passed_count'] += 1
                filtered_torrents.append(torrent)
        
        if verbose:
            console.print(f"\n[green]Filtering complete:[/green]")
            console.print(f"  [white]Total torrents checked: {filtering_stats['total_checked']}[/white]")
            console.print(f"  [green]Passed filtering: {filtering_stats['passed_count']}[/green]")
            console.print(f"  [red]Banned/filtered out: {filtering_stats['banned_count']}[/red]")
            
            if filtering_stats['by_group']:
                console.print(f"\n[yellow]Most common banned groups:[/yellow]")
                sorted_groups = sorted(filtering_stats['by_group'].items(), key=lambda x: x[1], reverse=True)
                for group, count in sorted_groups[:10]:  # Top 10
                    console.print(f"  [white]{group}: {count} torrents[/white]")
        
        return filtered_torrents, banned_torrents, filtering_stats
    
    def get_stats_summary(self, filtering_stats):
        """Get a summary of filtering statistics."""
        if not filtering_stats:
            return "No filtering performed"
        
        total = filtering_stats['total_checked']
        banned = filtering_stats['banned_count']
        passed = filtering_stats['passed_count']
        
        if total == 0:
            return "No torrents to filter"
        
        banned_percentage = (banned / total) * 100
        
        summary = f"Filtered {banned}/{total} torrents ({banned_percentage:.1f}%) with banned release groups"
        
        if filtering_stats['by_group']:
            top_group = max(filtering_stats['by_group'].items(), key=lambda x: x[1])
            summary += f". Most common: {top_group[0]} ({top_group[1]} torrents)"
        
        return summary


# Utility functions for integration with cross-pollinator

def create_banned_groups_checker(config, base_dir):
    """Create a BannedGroupsChecker instance."""
    return BannedGroupsChecker(config, base_dir)

async def filter_torrents_by_banned_groups(torrents, enabled_trackers, config, base_dir, verbose=False):
    """
    Main function to filter torrents by banned release groups.
    This is the primary integration point for cross-pollinator.py
    """
    checker = BannedGroupsChecker(config, base_dir)
    return await checker.filter_banned_torrents(torrents, enabled_trackers, verbose)

def extract_release_group(torrent_name):
    """Standalone function to extract release group from torrent name."""
    checker = BannedGroupsChecker({}, "")
    return checker.extract_release_group_from_name(torrent_name)


# Example usage and testing
async def test_banned_groups_checker():
    """Test function to demonstrate usage."""
    # Mock config
    config = {
        'TRACKERS': {
            'AITHER': {'api_key': 'your_api_key_here'},
            'LST': {'api_key': 'your_api_key_here'}
        }
    }
    
    # Test torrents
    test_torrents = [
        {'name': 'Movie.2023.1080p.BluRay.x264-SPARKS'},
        {'name': 'Show.S01E01.720p.WEB-DL.x264-FGT'},
        {'name': 'Another.Movie.2023.2160p.WEB-DL.x265-RARBG'},
        {'name': 'TV.Show.S02.Complete.1080p.WEB-DL.H264-GROUP'}
    ]
    
    checker = BannedGroupsChecker(config, '/tmp')
    
    # Test release group extraction
    for torrent in test_torrents:
        group = checker.extract_release_group_from_name(torrent['name'])
        print(f"'{torrent['name']}' -> Group: '{group}'")
    
    # Test filtering (would need real API keys)
    # filtered, banned, stats = await checker.filter_banned_torrents(test_torrents, ['AITHER', 'LST'], verbose=True)
    # print(f"\nFiltering results: {checker.get_stats_summary(stats)}")

if __name__ == "__main__":
    asyncio.run(test_banned_groups_checker())
