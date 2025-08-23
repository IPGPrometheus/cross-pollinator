# Cross-Pollinator: Maximize Your Seed

Cross-Pollinator is a Python script/Docker container that analyzes your [cross-seed](https://github.com/cross-seed/cross-seed) database to find torrents you are seeding that are **missing** from trackers you are on. It tells you what trackers your files are found or not found on and can output a nice, simple list of pre-written commands for [Audionut's Upload Assistant](https://github.com/Audionut/Upload-Assistant).


> [!WARNING]
> It does not validate your uploads, it does not validate your files.
> 
> **YOU, AND ONLY YOU, ARE RESPONSIBLE FOR FOLLOWING THE RULES OF THE TRACKERS YOU ARE ON. THIS MEANS FOLLOWING ALL THE RULES PRESENT ON THE SITES YOU UPLOAD TO.**

## Sample Output
```bash
🎬 Missing Video Files by Tracker:
================================================================================

🎬️  12.Angry.Men.1997.1080p.BluRay.FLAC2.0.x264-NTb.mkv
   📁 Path: /data/torrents/movies
   ❌ Missing from: HUNO, OE, OTW, SP
   ✅ Found on: AITHER, ANT, BLU, LST, ULCX

🎬️  12.Years.a.Slave.2013.1080p.BluRay.DTS.x264-SbR.mkv
   📁 Path: /data/torrents/movies
   ❌ Missing from: HUNO, LST, OE, OTW, SP
   ✅ Found on: AITHER, ANT, BLU, LST, ULCX

🎬️  2001.A.Space.Odyssey.1968.1080p.MAX.WEB-DL.DDP5.1.DV.HDR.H.265-Kitsune.mkv
   📁 Path: /data/torrents/movies
   ❌ Missing from: LST, OE, OTW, SP, ULCX
   ✅ Found on: AITHER, ANT, BLU, HUNO
```

### Output File:

```bash
# Cross-Pollinator: Generated <datetime>
# Total files needing upload: 552
# Note this is a build line for existing torrents on trackers.
# If you need to change anything, please add -tmdb TV/number or -tmdb movie/number or -tvdb number

# 12.Angry.Men.1997.1080p.BluRay.FLAC2.0.x264-NTb.mkv
# Missing from: HUNO, OE, OTW, SP
# Found on: AITHER, ANT, BLU, LST, ULCX
python3 upload.py "/data/torrents/movies/12.Angry.Men.1997.1080p.BluRay.FLAC2.0.x264-NTb.mkv" --trackers AITHER,ANT,BLU,LST,ULCX

# 12.Years.a.Slave.2013.1080p.BluRay.DTS.x264-SbR.mkv
# Missing from: HUNO, LST, OE, OTW, SP
# Found on: AITHER, ANT, BLU, LST, ULCX
python3 upload.py "/data/torrents/movies/12.Years.a.Slave.2013.1080p.BluRay.DTS.x264-SbR.mkv" --trackers HUNO,LST,OE,OTW,SP

# 2001.A.Space.Odyssey.1968.1080p.MAX.WEB-DL.DDP5.1.DV.HDR.H.265-Kitsune.mkv
# Missing from: LST, OE, OTW, SP, ULCX
# Found on: AITHER, ANT, BLU, HUNO
python3 upload.py "/data/torrents/movies/2001.A.Space.Odyssey.1968.1080p.MAX.WEB-DL.DDP5.1.DV.HDR.H.265-Kitsune.mkv" --trackers LST,OE,OTW,SP,ULCX
```

## Installation

### Docker

**Install with Docker Compose**

```bash
cd /path/to/docker/appdata

git clone https://github.com/IPGPrometheus/cross-pollinator.git

cd cross-pollinator

docker compose up -d
```

### Unraid

1. Download the [Docker Compose Manager](https://forums.unraid.net/topic/114415-plugin-docker-compose-manager/) from the app store.
2. Open the terminal and type the following:

   ```bash
   cd /mnt/user/appdata
   ```

   ```bash
   git clone https://github.com/IPGPrometheus/cross-pollinator.git
   ```
3. Head over to the Docker tab and go to Compose at the bottom. Click on **Add New Stack.**
4. Give it a name, click on **Advanced**, then set the stack directory `/mnt/user/appdata/cross-pollinator` as the installation location. Click **OK**.
5. Click the gear icon next to the name, then **Edit Stack** - **Compose File**. Make sure that the text editor is not empty and the stack shows up. 
6. Click **Save Changes**. 
7. Click **Compose Up**.

### Python

TBA

## Usage

Open the conatainer's console (Unraid) or type into the terminal

```bash
docker exec -it cross-pollinator bash
```

To run the program, type:

```bash
cross-pollinator --run [options]
```

Or, run directly from terminal:

```bash
docker exec -it cross-pollinator cross-pollinator --run [options]
```

### Options

```
Cross-Pollinator: Analyze your missing Torrents. Note this is a build line for existing torrents on trackers. If you need to change anything, please add -tmdb TV/number or -tmdb movie/number or -tvdb number

options:
  -h, --help         show this help message and exit
  --run              Run analysis and show missing torrents
  --output [OUTPUT]  Generate upload commands file [optional filename]
  --no-emoji         Remove all emojis from output (thanks Claude)
  --output-clean     Generate clean output with only upload commands. Add after --output
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and adjust:

`CROSS_SEED_DIR`: path to folder containing your `cross-seed.db`

`TZ`: [TZ Identifier](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)

### Tracker Mapping

The script includes comprehensive tracker mapping in `TRACKER_MAPPING`. Add new trackers as needed in `cross-pollinator.py`:

```python
TRACKER_MAPPING = {
    'NEWTRACKER': ['NEWTRACKER', 'newtracker-domain'],
    # ... existing mappings
}
```

### Config File

Create config/config.json in the container dir for tracker-specific validation rules.

```
{
  "TRACKERS": {
    "FL": {
      "min_file_size_mb": 100,
      "allowed_codecs": ["x264", "x265", "H.264", "HEVC"],
      "forbidden_filename_patterns": ["cam", "ts", "tc"]
    },
    "TL": {
      "min_file_size_mb": 50,
      "forbidden_filename_patterns": ["cam", "ts", "tc", "r5"],
      "min_duration_minutes": 60
    },
    "WhateverTrackerName": {
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
