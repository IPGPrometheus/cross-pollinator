# Cross-Pollinator

Cross-seed Missing Tracker Analyzer - Identifies torrents missing from specific trackers by analyzing cross-seed database records.

## What It Does

Cross-Pollinator analyzes your cross-seed database to find torrents that are **missing** from specific trackers.
This creates a nice, simple list with the CLI for UploadAssistant.

It does not validate your uploads, it does not validate your files. 

YOU, AND ONLY YOU, ARE RESPONSIBLE FOR FOLLOWING THE RULES OF THE TRACKERS YOU ARE ON. 
THIS MEANS FOLLOWING ALL THE RULES PRESENT ON THE SITES YOU UPLOAD TO. 

### Key Features

- **🎯 Missing Focus**: Only shows torrents missing from trackers (not ones already found.
- **🔍 Database Analysis**: Direct SQLite database analysis for accurate results
- **🐳 Docker Ready**: Full Docker setup for easy deployment
- **📊 Statistics**: Detailed upload statistics per tracker

## Quick Start

```bash
git clone https://github.com/yourusername/cross-pollinator.git
cd cross-pollinator
./setup.sh
./run.sh
```

## Sample Output

```
# Cross-Pollinator: Generated date time
# Total files needing upload: 617
 Note this is a build line for existing torrents on trackers. 
 If you need to change anything, please add -tmdb TV/number or -tmdb movie/number or -tvdb number 
# 10 Cloverfield Lane (2016) (1080p BluRay x265 Silence).mkv
# Missing from: FL
# Found on: TL
python3 upload.py "/data/onions/radarr/10 Cloverfield Lane (2016) (1080p BluRay x265 Silence).mkv" --trackers FL,TL
```

## Installation
1. **install with Docker Compose**
   ```
   cd /mnt/user/appdata or to the desired installation location. 
   git clone https://github.com/IPGPrometheus/cross-pollinator.git
   cd cross-pollinator

   docker-compose build cross-pollinator
   docker-compose up -d cross-pollinator 
    OR 
   using https://forums.unraid.net/topic/114415-plugin-docker-compose-manager/ 
     available on the App Store. 

   cd /mnt/user/appdata or to the desired installation location.  
   git clone https://github.com/IPGPrometheus/cross-pollinator.git

   Head over to the Docker tab - go to Compose at the bottom. Add New Stack
   Click Advanced, then set the stack directory as the installation location. 
   Name the stack. Click okay.
   Click the gear icon next to the name, then edit stack - edit compose file. Make sure that the docker compose shows up. 
   Close / Click Cancel. 

   Compose up 
   ```

## Usage
1. **Run Analysis**
   ```
   Cross-Pollinator: Analyze your missing Torrents. Note this is a build line for existing torrents on trackers. If you need to change anything, please add -tmdb TV/number     or -tmdb movie/number or -tvdb number

   options:
     -h, --help         show this help message and exit
     --run              Run analysis and show missing torrents
     --output [OUTPUT]  Generate upload commands file (optional filename)
     --no-emoji         Remove all emojis from output
     --output-clean     Generate clean output with only upload commands. Add after --output
   ```

### Manual run

```console
cross-pollinator.py --run [options]
```

```Command Line
docker exec -it cross-pollinator cross-pollinator.py --run [options]
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and adjust:

```bash
CROSS_SEED_DIR=/path/to/your/cross-seed
TZ=America/New_York
```

### Tracker Mapping

The script includes comprehensive tracker mapping in `TRACKER_MAPPING`. Add new trackers as needed:

```python
TRACKER_MAPPING = {
    'NEWTRACKER': ['NEWTRACKER', 'newtracker-domain'],
    # ... existing mappings
}
```

### Config File 

Create config/config.json in the container dir for tracker-specific validation rules.

```json
{
  "TRACKERS": {
    "BLU": {
      "min_file_size_mb": 100,
      "allowed_codecs": ["x264", "x265", "H.264", "HEVC"],
      "forbidden_filename_patterns": ["cam", "ts", "tc"]
    },
    "PTP": {
      "min_file_size_mb": 50,
      "forbidden_filename_patterns": ["cam", "ts", "tc", "r5"],
      "min_duration_minutes": 60
    },
    "HDB": {
      "min_file_size_mb": 200,
      "allowed_resolutions": ["720p", "1080p", "2160p"]
    }
  }
}

```

## How It Works

1. **Database Analysis**: Connects to `cross-seed.db`
2. **Deduplication**: Groups by `info_hash` to show each torrent once
3. **Success Filtering**: Identifies successful matches (`MATCH`, `MATCH_SIZE_ONLY`, `MATCH_PARTIAL`)
4. **Missing Calculation**: Compares found trackers vs configured trackers
5. **Clean Output**: Shows only torrents missing from at least one tracker

## Troubleshooting

### Database Not Found
```
❌ Database not found: /cross-seed/cross-seed.db
```
- Check your `CROSS_SEED_DIR` path in `.env`
- Ensure cross-seed container is running and has created database

### No Configured Trackers
```
❌ No configured trackers found
```
- Run cross-seed searches first to populate database
- Check if your tracker names match the `TRACKER_MAPPING`

### Unknown Trackers
The script filters out unmapped trackers like `concertos`, `www` to avoid noise. Add them to `TRACKER_MAPPING` if needed.

## Development

### Project Structure
```
cross-pollinator/
├── cross-pollinator.py    # Main application
├── Dockerfile            # Container definition
├── docker-compose.yml    # Container orchestration
├── build.sh             # Build script
├── run.sh               # Run script
├── setup.sh             # Initial setup
├── .env.example         # Environment template
└── README.md            # This file
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with your cross-seed setup
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

- Check the [Issues](https://github.com/yourusername/cross-pollinator/issues) page
- Create a new issue with your cross-seed setup details
- Include sample output and error messages
