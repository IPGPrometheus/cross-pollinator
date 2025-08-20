# Cross-Pollinator

Cross-seed Missing Tracker Analyzer - Identifies torrents missing from specific trackers by analyzing cross-seed database records.

## What It Does

Cross-Pollinator analyzes your cross-seed database to find torrents that are **missing** from specific trackers.

### Key Features

- **🎯 Missing Focus**: Only shows torrents missing from trackers (not ones already found.
- **🏷️ Tracker Normalization**: Clean tracker abbreviations (FL, BLU, AITHER, etc.)
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
Cross-Pollinator: Missing Tracker Analyzer
==========================================
📊 Found 2 unique torrents missing from trackers
🎯 Configured trackers: AITHER, BLU, FL, HUNO, LST, OE, OTW

🔍 MISSING TRACKER REPORT:
================================================================================
Wonder.2017.1080p.UHD.BluRay.DDP.7.1.HDR.x265.D-Z0N3.mkv | missing from | BLU, HUNO, LST
Movie.2024.2160p.WEB.H265-SLOT.mkv | missing from | AITHER, FL, OTW
================================================================================
📈 Total files needing upload: 2
```

## Installation & Usage

### Docker (Recommended)

1. **Initial Setup**
   ```bash
   ./setup.sh
   ```

2. **Run Analysis**
   ```bash
   ./run.sh                    # Basic analysis
   ./run.sh --stats           # With detailed statistics
   ```

3. **Manual Build** (if needed)
   ```bash
   ./build.sh                 # Build Docker image
   ```

### Manual Installation

```bash
python3 cross-pollinator.py --run --stats
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
